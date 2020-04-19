import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload

from general_utils import smkdir

AUTH_PATH = "auth"

FILES_FULL_ACCESS       =   "https://www.googleapis.com/auth/drive"
METADATA_FULL_ACCESS    =   "https://www.googleapis.com/auth/drive.metadata"
METADATA_READ_ONLY       =   "https://www.googleapis.com/auth/drive.metadata.readonly"

class GoogleDrive(object):
    def __init__(self):
        self._creds = self._prepare_credentials()
        self._service = build('drive', 'v3', credentials=self._creds)

    def _prepare_credentials(self):
        creds = None
        if not smkdir(AUTH_PATH):
            return False

        token_file_path = os.path.join(AUTH_PATH, 'token.pickle')
        cred_file_path = os.path.join(AUTH_PATH, 'credentials.json')

        if os.path.exists(token_file_path):
            with open(token_file_path, 'rb') as token:
                creds = pickle.load(token)

        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())

            else:
                flow = InstalledAppFlow.from_client_secrets_file(cred_file_path, [FILES_FULL_ACCESS,
                                                                                  METADATA_FULL_ACCESS])
                creds = flow.run_local_server(port=0)

            # Save the credentials for the next run
            with open(token_file_path, 'wb') as token:
                pickle.dump(creds, token)

        return creds

    def get_file_matches(self, filename):
        """

        :return: file with its tree, None if not exist.
        example: [
        {u'mimeType': u'application/vnd.google-apps.shortcut',
         u'id': u'1tSk-Y7EYyYIuEruhto2rM760Be5jzcMB',
         u'name': u'Zeligs photos'},
          {u'mimeType': u'application/vnd.google-apps.folder',
           u'id': u'1Efb7OjAXrhbHLr8k83sCmd0wTCNAl0jL',
           u'name': u'Zeligs photos'}]

        """
        if not filename:
            return []
        results = self._service.files().list(q="name contains '%s' and not trashed" % filename,
                                             pageSize=100,
                                             fields="nextPageToken , files(mimeType, id, name, md5Checksum, parents)").execute()
        # results = self._service.files().list(spaces='drive', pageSize=50, ).execute()
        items = results.get('files', [])

        if not items:
            print("[-] Could not find %s." % filename)
            return []
        else:
            print("[+] Found %d matches to %s." % (len(items), filename))
            return items

    def create_folder(self, name, parent_id=None):
        file_metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder'
        }

        # Worth to be noted: API V3 uses list, while V2 uses dict [{"id" : id}]
        if parent_id:
            file_metadata["parents"] = [parent_id]
        file = self._service.files().create(body=file_metadata,
                                            fields='id').execute()
        print '[+] Created folder with ID: %s' % file.get('id')
        return file.get('id')

    def upload_file_to_folder(self, file_path, folder_id):
        file_metadata = {
            'name': os.path.basename(file_path),
            'parents': [folder_id]
        }
        media = MediaFileUpload(file_path,
                                # mimetype='image/jpeg',
                                resumable=True)
        file = self._service.files().create(body=file_metadata,
                                            media_body=media,
                                            fields='id').execute()
        print('[+] Uploaded file %s to folder with id %s, file id is: %s' % (file_path, folder_id, file.get('id')))
        return file.get('id')

    def _get_permissions_by_file_id_email(self, file_id, email=None):
        # So, permission is for specific person
        try:
            response = self._service.permissions().list(fileId=file_id,#q="emailAddress contains '%s'" % email,
                                             pageSize=100,
                                             fields="nextPageToken , permissions(id, type, emailAddress, role)").execute()

            if email:
                result = filter(lambda s: "emailAddress" in s.keys() and s["emailAddress"] == email, response["permissions"]) \
                    if response else None

            else:
                result = response["permissions"]

            if result:
                print "[+] Got id %s for email %s." % (result[0]["id"], email)
                return result

            return None

        except Exception as e:
            print "[-] Error: Could not get id for email %s." % email
            print e
            return None

    def _update_permissions_for_file_id(self, file_id, permission, new_role):
        try:
            # permission is like one person, so we add the role_to_add to the person who own
            updated_perm = self._service.permissions().update(fileId=file_id, permissionId=permission["id"],
                                                              body={"role": new_role},
                                                              transferOwnership=(new_role == "owner")).execute()

            print "[+] Updated permission. new_role: %s, file_id: %s, permissions_id: %s" % (new_role, file_id,
                                                                                             permission["id"])
            return updated_perm

        except Exception as e:
            print "[-] Failed to update permission. new_role: %s, file_id: %s, permissions_id: %s" % (new_role,
                                                                                                      file_id,
                                                                                                      permission["id"])
            print e
            return None

    def set_email_to_file_owner(self, file_id, email):
        print "[+] Trying to set owner %s to file id %s" % (email, file_id)
        perms = self._get_permissions_by_file_id_email(file_id, email)
        print "[+] Got permissions to email and file id."

        for perm in perms:
            if perm["role"] == "owner":
                print "[+] %s already the owner of file id %s" % (email, file_id)
                return True

        if perms:
            # well... there should only be one perm, whats the harm of sending index 0...
            if self._update_permissions_for_file_id(file_id, perms[0], "owner"):
                return True

        print "[-] Failed to set owner."
        return False