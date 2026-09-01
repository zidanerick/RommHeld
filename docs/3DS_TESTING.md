# Nintendo 3DS FTP testing

This document covers the first physical test of the RommHeld 3DS backend.

## 3DS side

RommHeld expects an FTP server running on the 3DS. The `mtheall/ftpd` project is a suitable upstream option and normally uses port `5000`; use the host and port displayed/configured by the FTP server rather than assuming a fixed address.

Upstream FTPD:

`https://github.com/mtheall/ftpd`

For a first test, run the regular FTPD homebrew application rather than installing the background sysmodule. The goal is only to prove the Linux-to-3DS transfer path.

The Linux computer and 3DS should be on the same local network.

## RommHeld side

Use the feature branch that contains the 3DS FTP implementation.

```fish
cd ~/romm-vita-manager
git fetch origin
git checkout feature/3ds-ftp
git pull
./run.sh
```

The local directory name may remain `romm-vita-manager` during the branding transition.

Select **3DS FTP** from the main window.

Enter:

- Host: the IP address shown by the 3DS FTP server
- Port: the port shown by the 3DS FTP server, commonly `5000`
- Username/password: leave at the server's documented defaults when it uses anonymous access

Click **Connect**.

Once connected, RommHeld should display the remote directory listing.

## Safe first transfer

Do not start with a ROM.

Create a small local test file:

```fish
printf 'RommHeld 3DS FTP test\n' > /tmp/rommheld-3ds-test.txt
```

In RommHeld:

1. choose `/tmp/rommheld-3ds-test.txt`
2. browse to a safe directory on the 3DS
3. set the remote filename to `rommheld-3ds-test.txt`
4. click **Send File**

The UI should report that the upload completed and was size-verified.

Then use the 3DS filesystem/homebrew tools or reconnect through FTP to confirm the file exists and has the expected contents.

## Repeatability tests

After the first successful transfer:

1. Send the same file again. RommHeld should report that the same-size remote file was skipped.
2. Change the local test file contents so its size differs. RommHeld should not silently overwrite the existing remote file.
3. Test an interrupted transfer with a larger file, then retry it. The backend supports resume when the FTP server accepts `REST` for uploads.
4. Navigate into a directory and back out using the remote browser.

## Notes about FTP server compatibility

RommHeld intentionally does not depend on optional FTP commands such as `MDTM`. The 3DS `ftpd` project has an open issue showing that `MDTM` can return `502 Command not implemented` on current 3DS builds.

The backend prefers `MLSD` directory listings but falls back to `NLST` and directory probing for servers that do not provide `MLSD`.

FTP is unencrypted. Use it on a trusted local network and do not expose the 3DS FTP server directly to the Internet.

## Expected result

The milestone is successful when RommHeld can:

```text
Linux
  ↓
RommHeld
  ↓
FTP
  ↓
3DS
  ↓
remote file
```

with successful connection, browsing, upload, skip, and post-upload size verification.
