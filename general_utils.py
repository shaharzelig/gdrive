import hashlib
import os

def smkdir(path):
    try:
        if not os.path.isdir(path):
            os.mkdir(path)
    except:
        return False
    return True


def md5file(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()