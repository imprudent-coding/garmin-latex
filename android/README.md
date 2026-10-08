# App Android companion

Kotlin + Jetpack Compose, minSdk 26, compileSdk 36. Versioni di plugin e librerie
in [`gradle/libs.versions.toml`](gradle/libs.versions.toml).

```bash
./gradlew testDebugUnitTest assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

La build di debug ha id `io.github.imprudentcoding.garminlatex.debug` e può stare
accanto a quella firmata. Per firmare la release in locale imposta
`ANDROID_KEYSTORE_PATH`, `ANDROID_KEYSTORE_PASSWORD` e `ANDROID_KEY_ALIAS`
(stesse variabili usate dalla CI).

## Struttura

| Package | Ruolo |
|---|---|
| `bundle/` | `BundleRepository`: cerca l'ultima Release `notes-*` con `notes-bundle.zip` (API GitHub, repo pubblico), scarica, verifica schema e hash di ogni risorsa e sostituisce il bundle in modo atomico. `Bundle`: lettura dello zip |
| `watch/` | `ProtocolHandler`: risposte a `hello`/`get` (pura, con unit test). `WatchLink`: Connect IQ Mobile SDK 2.4.0 (stato SDK, dispositivi, app installata, invio con retry, avviso `update`). `WatchService`: servizio in primo piano |
| `work/` | `UpdateWorker`: controllo periodico (WorkManager, solo con rete) e notifica |
| `render/` | `PageRenderer`: anteprima delle pagine con gli stessi font bitmap dell'orologio |
| `ui/` | schermate Compose: stato, anteprima, impostazioni |

L'UUID dell'app orologio viene letto da [`../shared/app-id.txt`](../shared/app-id.txt)
in fase di build (`BuildConfig.WATCH_APP_ID`): deve coincidere con
`garmin/manifest.xml`.

## Casi gestiti

- Garmin Connect non installato o da aggiornare: messaggio e pulsante per il Play Store.
- Nessun orologio associato, orologio non connesso: stato aggiornato dagli eventi
  dell'SDK.
- App orologio non installata: messaggio con le istruzioni. Per le app installate
  via USB lo stato potrebbe non essere affidabile.
- Messaggio troppo grande (`FAILURE_MESSAGE_TOO_LARGE`): indicazione nel registro
  di ridurre `chunk_bytes`.
- Simulatore Connect IQ: impostazione «Simulatore» (`IQConnectType.TETHERED`, ADB
  porta 7381).
