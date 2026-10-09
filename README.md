# NUTRINUTS

A runnable desktop storefront for premium dry fruits. The app uses Python's
built-in Tk interface and SQLite, so it can be started on Windows without
installing packages or setting up Firebase, Razorpay, or Flutter.

## Run on Windows

Open PowerShell in this folder and run:

```powershell
.\venv\Scripts\python.exe .\main.py
```

If you are not using the included virtual environment, run `python main.py`
with Python 3.10 or newer. The app opens a desktop window.

## Included features

- Product catalogue with categories, search, prices, and ratings
- Add products to a basket and change quantities
- Checkout with name, phone number, and delivery address validation
- Cash-on-delivery orders and order history
- Local persistence: products, basket, and orders are saved in `nutrinuts.db`
- No login, network connection, or external credentials required

Set `NUTRINUTS_DB_PATH` before launching to choose a different SQLite database
location. If the database file is removed, the app creates a fresh catalogue
the next time it starts.

## Project files

```text
main.py          Desktop application and SQLite data store
requirements.txt Original optional service/mobile dependency list
README.md        Setup and usage instructions
```

The Firebase authentication, Firestore synchronization, Razorpay online
payments, FastAPI service, and Android/iOS builds described in the original
project plan are not part of this local runnable version. Online payments are
not simulated; checkout clearly uses cash on delivery.
