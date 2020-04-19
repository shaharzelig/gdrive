# -*- coding: utf-8 -*-
import os.path
from google_drive import GoogleDrive
from general_utils import md5file

FOLDER_MIMETYPE = "application/vnd.google-apps.folder"

class UploadFolder(GoogleDrive):
    def __init__(self):
        self._files_ids = {}
        self._folders_ids = {}
        super(UploadFolder, self).__init__()

    def _is_parent_of_file(self, file_object, parent_id):
        # if parent_id is null, it means we do not want to really filter
        if not parent_id:
            return True

        if file_object:
            if "parents" in file_object.keys():
                return parent_id in file_object["parents"]
        return False

    def _is_folder(self, match):
        if match:
            if "mimeType" in match.keys():
                if match["mimeType"] == FOLDER_MIMETYPE:
                    return True
        return False

    def get_folder_id(self, folder_name, parent_id=None):
        data = self.get_file_matches(folder_name)
        result = filter(lambda m: self._is_parent_of_file(m, parent_id), filter(self._is_folder, data))

        # IDK, i think it as to have at least one...
        return result[0]["id"] if result else None

    def get_matched_hash(self, matches, md5):
        for match in matches:
            if "md5Checksum" in match.keys():
                if match["md5Checksum"] == md5:
                    return match
        return None

    def upload_folder(self, folder_path, parent_folder_name=None, owner=None):
        folder_name = os.path.basename(folder_path)

        parent_id = self.get_folder_id(parent_folder_name)
        folder_id = self.get_folder_id(folder_name, parent_id)

        if not folder_id:
            folder_id = self.create_folder(folder_name, parent_id)

        folders_ids = {folder_name: folder_id}
        files_ids = {}
        for root, dirs, files in os.walk(unicode(folder_path)):
            root_name = os.path.basename(root)
            if root_name in folders_ids.keys():
                root_id = folders_ids[root_name]
                print("[+] root %s already exist. id: %s" % (root, root_id))

            else:
                print("[+] Creating root folder: %s" % root)
                root_id = self._service.create_folder(os.path.basename(folder_path))

            if owner:
                self.set_email_to_file_owner(root_id, owner)

            print("[+] Going through dirs of root %s:" % root)
            for dir in dirs:
                if dir in folders_ids.keys():
                    dir_id = folders_ids[dir]
                    print("[+] dir %s already exist. id: %s" % (dir, dir_id))

                else:
                    dir_id = self.get_folder_id(dir, root_id)


                if not dir_id:
                    dir_id = self.create_folder(dir, root_id)

                folders_ids[dir] = dir_id
                if owner:
                    self.set_email_to_file_owner(dir_id, owner)

            for filename in files:
                print "[+] Checking file %s filename" % filename
                if filename in files_ids.keys():
                    file_id = files_ids[filename]

                else:
                    file_data = self.get_file_matches(filename)
                    relevant_files_to_root_parent = filter(lambda m: self._is_parent_of_file(m, root_id), file_data)
                    current_md5 = md5file(os.path.join(root, filename))
                    md5_match = self.get_matched_hash(relevant_files_to_root_parent, current_md5)
                    if md5_match:
                        print("[+] Found file %s with same MD5: %s. continuing..." % (filename, current_md5))
                        file_id = md5_match["id"]

                    else:
                        file_id = relevant_files_to_root_parent[0]["id"] if relevant_files_to_root_parent else None

                if not file_id:
                    abs_path = os.path.join(root, filename)
                    print("[+] Uploading %s to parent_id: %s" % (abs_path, root_id))
                    file_id = self.upload_file_to_folder(abs_path, root_id)

                if owner:
                    self.set_email_to_file_owner(file_id, owner)


if __name__ == '__main__':
    new_owner = "mail@gmail.com"
    folder_path_to_upload = r"C:\upload_me"
    drive_folder_destination = "my_fast_uploads"

    uf = UploadFolder()
    uf.upload_folder(folder_path_to_upload, drive_folder_destination, new_owner)