import argparse
import sys



import paramiko


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="192.168.137.99")
    parser.add_argument("remote")
    parser.add_argument("local")
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
        with client.open_sftp() as sftp:
            sftp.get(args.remote, args.local)
    finally:
        client.close()


if __name__ == "__main__":
    main()
