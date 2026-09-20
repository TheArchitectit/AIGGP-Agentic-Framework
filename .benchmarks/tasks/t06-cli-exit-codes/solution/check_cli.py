import sys


def main(argv):
    if len(argv) < 1:
        print("usage: check <value>")
        return 1
    value = argv[0]
    if value == "good":
        print("OK")
        return 0
    print("FAIL")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
