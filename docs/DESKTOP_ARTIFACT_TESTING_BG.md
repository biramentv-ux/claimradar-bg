# ClaimRadar BG — Desktop artifact testing before sharing EXE

Този документ описва правилото за бъдещи desktop release-и: не се изпраща `.exe` към потребителя без проверка.

## Защо ZIP, не 7z

GitHub Actions artifact-ите стандартно се свалят като `.zip`. Тази чат/sandbox среда може да проверява ZIP с Python standard library. Ако artifact-ът бъде преопакован като `.7z`, средата може да няма 7-Zip extractor и проверката няма да може да извлече файловете.

## Smoke helper

```bash
python scripts/test_desktop_artifact.py path/to/ClaimRadarBG-Windows-Desktop.zip --json
```

Проверява:

```text
дали има desktop ClaimRadar .exe
дали има claimradar_backend.exe
дали backend layout-ът изглежда съвместим с Electron launcher-а
дали artifact-ът е zip/extracted folder
```

На Windows може да се пусне и runtime smoke:

```bash
python scripts/test_desktop_artifact.py path/to/ClaimRadarBG-Windows-Desktop.zip --runtime --json
```

Това стартира backend exe и проверява:

```text
http://127.0.0.1:8765/api/local-ai/status
```

## Нов workflow за работа в чата

1. Build artifact от GitHub Actions.
2. Качи оригиналния `.zip` artifact тук в чата.
3. Асистентът пуска `scripts/test_desktop_artifact.py` върху ZIP-а.
4. Ако layout-ът е OK, асистентът извлича правилния `.exe` и го връща като директен download link.
5. Ако има грешка, първо се поправя кодът/build pipeline-ът.
