# ClaimRadar BG — Desktop artifact testing before sharing EXE

Този документ описва правилото за бъдещи desktop release-и: не се изпраща `.exe` към потребителя без проверка.

## Поддържани artifact формати

Smoke helper-ът вече поддържа:

```text
.zip
.7z
разархивирана папка
```

За `.zip` се използва Python standard library `zipfile`.

За `.7z` се използва `py7zr`:

```bash
pip install py7zr
```

`requirements-dev.txt` вече включва `py7zr`, така че CI/dev средата може да извлича `.7z` artifact-и.

## Smoke helper

```bash
python scripts/test_desktop_artifact.py path/to/ClaimRadarBG-Windows-Desktop.zip --json
python scripts/test_desktop_artifact.py path/to/ClaimRadarBG-Windows-Desktop.7z --json
```

Проверява:

```text
дали има desktop ClaimRadar .exe
дали има claimradar_backend.exe
дали backend layout-ът изглежда съвместим с Electron launcher-а
дали artifact-ът е zip/7z/extracted folder
дали archive paths са безопасни за extract
```

На Windows може да се пусне и runtime smoke:

```bash
python scripts/test_desktop_artifact.py path/to/ClaimRadarBG-Windows-Desktop.7z --runtime --json
```

Това стартира backend exe и проверява:

```text
http://127.0.0.1:8765/api/local-ai/status
```

## Нов workflow за работа в чата

1. Build artifact от GitHub Actions.
2. Качи `.zip` или `.7z` artifact тук в чата.
3. Асистентът пуска `scripts/test_desktop_artifact.py` върху artifact-а.
4. Ако layout-ът е OK, асистентът извлича правилния `.exe` и го връща като директен download link.
5. Ако има грешка, първо се поправя кодът/build pipeline-ът.
