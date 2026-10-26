import argparse
import sys



import paramiko


HOST = "192.168.137.99"
USER = "xilinx"
PASSWORD = "xilinx"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=HOST)
    parser.add_argument("command", nargs="?")
    parser.add_argument("--file")
    parser.add_argument("--sudo", action="store_true")
    args = parser.parse_args()

    if bool(args.command) == bool(args.file):
        parser.error("provide exactly one of command or --file")
    command = args.command
    if args.file:
        with open(args.file, "r", encoding="utf-8") as stream:
            command = stream.read()
    payload = None
    if args.sudo:
        payload = PASSWORD + "\n" + command + "\n"
        command = "sudo -S -p '' sh"

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        args.host,
        username=USER,
        password=PASSWORD,
        timeout=30,
        banner_timeout=30,
        auth_timeout=30,
    )
    try:
        stdin, stdout, stderr = client.exec_command(command, timeout=120)
        if payload is not None:
            stdin.write(payload)
            stdin.flush()
            stdin.channel.shutdown_write()
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        code = stdout.channel.recv_exit_status()
        if out:
            print(out, end="")
        if err:
            print(err, end="", file=sys.stderr)
        raise SystemExit(code)
    finally:
        client.close()


if __name__ == "__main__":
    main()
