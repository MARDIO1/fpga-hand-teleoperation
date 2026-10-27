import argparse
import os
import sys



import paramiko


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="192.168.137.99")
    parser.add_argument("local")
    parser.add_argument("remote")
    args = parser.parse_args()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        args.host,
        username="xilinx",
        password="xilinx",
        timeout=30,
        banner_timeout=30,
        auth_timeout=30,
    )
    try:
        size = os.path.getsize(args.local)
        last_percent = -1

        def progress(transferred, total):
            nonlocal last_percent
            percent = int(transferred * 100 / total)
            if percent // 10 != last_percent // 10:
                print(f"{percent}% ({transferred}/{size} bytes)", flush=True)
                last_percent = percent

        with client.open_sftp() as sftp:
            sftp.put(args.local, args.remote, callback=progress, confirm=True)
    finally:
        client.close()


if __name__ == "__main__":
    main()
