import argparse
import json
import subprocess
import sys
import tarfile


def extract_repotag_from_tar(tarpath):
    tar = tarfile.open(tarpath)
    manifest = tar.getmember("manifest.json")
    f = tar.extractfile(manifest)
    assert f is not None
    j_data = json.load(f)

    return j_data[0]["RepoTags"][0]


def docker_image_present(repotag):
    proc = subprocess.run(
        ["docker", "image", "inspect", repotag],
        stderr=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
    )
    return proc.returncode == 0


def main(tarpath, force):
    repotag = extract_repotag_from_tar(tarpath)

    if not docker_image_present(repotag) or force:
        try:
            output = subprocess.check_output(f"docker load < {tarpath}", shell=True).decode(
                "utf-8"
            )
        except subprocess.CalledProcessError:
            print("The docker container failed to load...")
            sys.exit(1)

        # return the image ID
        print(output.replace("Loaded image: ", "").strip(), end="")
        sys.exit(2)
    else:
        # return the image tag
        print(repotag.strip(), end="")
        sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "tarpath", type=str, help="Path to the tar'd image that you want to load"
    )
    parser.add_argument(
        "--force", required=False, action="store_true", help="force load the container even if the tag exists"
    )

    args = parser.parse_args()
    main(args.tarpath, args.force)
