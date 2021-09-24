import ftplib
import glob
import logging
import os
import sys
from datetime import datetime

from optparse import OptionParser
from pathlib import Path

# This is a private local file "creds.py" which contains the login details for your FTP server.
# Arguably using dotenv would be more normal, but requires a bit more work and a non-standard library.
# It takes the following form:
# SERVER="ftp.domain.com"
# USER="user@domain.com"
# PSWRD="password"
# LAST_UPDATE_FILENAME="lastupdate.txt"
import creds


SUB_PATHS = [
    # sub_path, file_spec, permissions (int)
    ("", "*.html", 664),
    ("author", "*.html", 664),
    ("category", "*.html", 664),
    ("feeds", "*.xml", 664),
    ("images", "*.jpg", 644),
    ("images", "*.jpeg", 644),
    ("images", "*.png", 644),
    ("images", "*.gif", 644),
    ("pages", "*.html", 664),
    ("tags", "*.html", 664),
    ("theme/css", "*.css", 644),
    ("theme/fonts", "*.otf", 644),
    ("theme/fonts", "*.ttf", 644),
    ("theme/images", "*.jpg", 644),
    ("theme/images", "*.png", 644),
    ("theme/js", "*.js", 644),
]


def upload_file(ftp_connection, local_path, filename, remote_base, sub_path, permissions_int):
    """
    Uploads a local file to a remote path and sets permissions
    ftp_connection should already be logged in, etc.
    """
    remote_path = os.path.join("/", remote_base, sub_path)
    try:
        with open(local_path, "rb") as fp:
            ftp_connection.cwd(remote_path)
            logging.debug(f"Changed directory to {remote_path}")
            res = ftp_connection.storbinary("STOR " + filename, fp)
            if not res.startswith("226"):
                logging.error(f"FAILURE uploading '{filename}'")
                logging.error(res)
            else:
                logging.info(f"Uploaded '{filename}' to {remote_path}")
                res2 = ftp_connection.sendcmd(f"SITE CHMOD {permissions_int} " + filename)
                logging.debug(f"Permissions change: '{res2}'")
    except ftplib.all_errors as e:
        logging.error(f"FTP Error: '{e}'")

    # return to root path (from an FTP POV)
    ftp_connection.cwd(os.path.join("/", remote_base))


def check_and_upload_files(source_path, remote_base, force_update):
    if os.path.exists(creds.LAST_UPDATE_FILENAME):
        last_update_date_time = os.path.getmtime(creds.LAST_UPDATE_FILENAME)
    else:
        # Bodge: If the file does not exist, set a very old last update date to force all files to update.
        last_update_date_time = 0
    logging.info(f"Last update date/time={datetime.utcfromtimestamp(last_update_date_time).isoformat()}")
    count = 0

    with ftplib.FTP(host=creds.SERVER, user=creds.USER, passwd=creds.PSWRD) as ftp:
        logging.debug(f"Logged into '{creds.SERVER}'")
        for sub_path, file_spec, perms_int in SUB_PATHS:
            for fs_obj in glob.glob(os.path.join(source_path, sub_path, file_spec)):
                # Only upload files changed since last update.
                if force_update or os.path.getmtime(fs_obj) > last_update_date_time:
                    file_name = os.path.basename(fs_obj)
                    upload_file(
                        ftp_connection=ftp,
                        local_path=fs_obj,
                        filename=file_name,
                        remote_base=remote_base,
                        sub_path=sub_path,
                        permissions_int=perms_int
                    )
                    count += 1

    logging.info(f"Uploaded {count} files.")
    if count > 0:
        # Update the modification date to now.
        Path(creds.LAST_UPDATE_FILENAME).touch()


def handle_options():
    """ Processes the command-line parameters returning resulting variables. """
    ops = OptionParser(usage="pelican_ftp.py [options]")
    ops.add_option("--source_path", "-s",
                   action="store", dest="source_path", default="",
                   help="Path to Pelican output directory.")
    ops.add_option("--remote_base", "-r", action="store",
                   dest="remote_base", default="",
                   help="The base directory on the FTP server to store the files.")
    ops.add_option("--force_update", "-f", action="store_true", dest="force_update",
                   default=False,
                   help="Update (overwrite) files even if they are unchanged since the last update. "
                        "Note: does not check dates of remote files.")
    ops.add_option("--log-level", "-l", action="store", dest="log_level", choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                   help="Set the logging level")

    # Throw away any spare parameters.
    options, _ = ops.parse_args()

    if options.log_level:
        logging.basicConfig(level=getattr(logging, options.log_level))
    else:
        logging.basicConfig(level=logging.INFO)

    if options.source_path == '':
        logging.error("No source specified - nothing to do!")
        sys.exit(1)

    return options.source_path, options.remote_base, options.force_update


def main():
    """
    Main entry point where it all kicks off.
    """
    source_path, remote_base, force_update = handle_options()
    check_and_upload_files(source_path=source_path, remote_base=remote_base, force_update=force_update)


if __name__ == '__main__':
    main()
