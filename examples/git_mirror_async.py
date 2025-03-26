import asyncio

from repligit.asyncio import fetch_pack, ls_remote, send_pack


async def main():
    src_remote_url = "https://github.com/spack/spack.git"
    dest_remote_url = "https://gitlab.com/test-org/test-repo.git"

    branch_name = "main"

    target_ref = f"refs/heads/{branch_name}"

    # note: provide credentials in the following situations:
    # ls_remote: source repo requires auth to read
    # ls_remote: destination repo requires auth to read
    # fetch_pack: source repo requires auth to read
    # send_pack: destination repo requires auth to write
    src_username = "<username>"
    src_password = "<token>"
    dest_username = "<username>"
    dest_password = "<token>"

    gh_refs = await ls_remote(
        src_remote_url, username=src_username, password=src_password
    )
    gl_refs = ls_remote(dest_remote_url, username=dest_username, password=dest_password)

    want_sha = gh_refs[target_ref]
    have_shas = gl_refs.values()

    from_sha = gl_refs.get(target_ref) or ("0" * 40)

    if want_sha in have_shas:
        print("Everything is up to date")
        return

    packfile = await fetch_pack(
        src_remote_url,
        want_sha,
        have_shas,
        username=src_username,
        password=src_password,
    )

    await send_pack(
        dest_remote_url,
        target_ref,
        from_sha,
        want_sha,
        packfile,
        username=dest_username,
        password=dest_password,
    )


if __name__ == "__main__":
    asyncio.run(main())
