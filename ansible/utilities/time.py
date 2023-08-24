import argparse
import subprocess
import shutil
import sys


def get_datetime():
    print(subprocess.check_output(["date","+%s"]).decode("utf-8").strip(), end='')


def set_datetime(input_datetime: str):
    datetime = f"@{input_datetime}"
    subprocess.check_call(["date", "-s", datetime])


if __name__ == "__main__":
    if not shutil.which("date"):
        print("This requires a `date` program.")
        sys.exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["get", "set"], help="Mode to selet")
    parser.add_argument("--datetime", type=str, help="Datetime used when setting time")

    args = parser.parse_args()

    if args.mode == "get":
        get_datetime()
    elif args.mode == "set":
        set_datetime(args.datetime)
