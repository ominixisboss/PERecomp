# Signing: why new builds keep your save

Android installs an update over an existing app only if both are signed with
the **same key**. The CI used to sign every APK with a throwaway debug key made
fresh on each run, so a new build would not install over the old one: Android
said "App not installed" (or offered to uninstall first), and uninstalling
deletes the app's private storage -- including `pokeemerald.sav`.

The workflow now signs with one permanent key kept in two repository secrets:

| Secret | Value |
|---|---|
| `ANDROID_KEYSTORE_BASE64` | the keystore file, base64-encoded |
| `ANDROID_KEYSTORE_PASSWORD` | its password (store and key share it; alias `pokeemerald`) |

Add them under **Settings -> Secrets and variables -> Actions -> New repository
secret**. Without them, builds still work but fall back to a throwaway key and
the "Restore the signing key" step prints a warning.

The permanent key's certificate fingerprint (SHA-256) is

    54:0D:A3:C0:19:86:9C:15:3A:3B:AA:72:88:0E:46:D0:52:32:A8:2D:EB:36:F6:10:7D:7D:AC:5F:C5:5A:A4:AD

and the "Show the signing certificate" step checks every APK against it.

**Never commit the keystore.** Anyone holding it can sign an APK that installs
over yours and reads its data. Keep a copy of it (and the password) somewhere
safe: if it is lost, the next key change means one more uninstall.

## The one-time switch

An install signed with an old throwaway key cannot be updated by a build
signed with the permanent key -- Android sees a different signer. That last
transition needs an uninstall, so move the save across first:

1. In the *new* build there is a gear -> **Back up save**; the old build has
   no such button. If the old build is still installed, its save can be
   copied off with a computer: `adb shell run-as com.pokeemerald.experimental
   cat files/pokeemerald.sav > pokeemerald.sav` (works because debug builds
   are debuggable).
2. Uninstall the old app, install the new one, then gear -> **Restore save**
   and pick the file.

From then on every build installs over the last and the save stays put. As a
second safety net the app also copies the save to
`Downloads/PokemonEmerald/pokeemerald-backup.sav` whenever you leave it
(Android 10+), which survives even an uninstall.
