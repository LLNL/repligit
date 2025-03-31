from repligit import fetch_pack, ls_remote, send_pack


def main():
    src_remote_url = "https://github.com/spack/spack.git"
    dest_remote_url = "https://gitlab.com/test-org/test-repo.git"

    branch_name = "main"

    target_ref = f"refs/heads/{branch_name}"

    gh_refs = ls_remote(src_remote_url)
    gl_refs = ls_remote(dest_remote_url)

    want_sha = gh_refs[target_ref]
    have_shas = gl_refs.values()

    from_sha = gl_refs.get(target_ref) or ("0" * 40)

    if want_sha in have_shas:
        print("Everything is up to date")
        return

    packfile = fetch_pack(src_remote_url, want_sha, have_shas)

    dest_username = "<username>"
    dest_password = "<token>"

    send_pack(
        dest_remote_url,
        target_ref,
        from_sha,
        want_sha,
        packfile,
        username=dest_username,
        password=dest_password,
    )


if __name__ == "__main__":
    main()
