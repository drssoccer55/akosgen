# Notes

Using venv so if you need to change packages you'll have to enter the venv

Do `source ./venv/bin/activate`

Then you can do something like
`pip install PySide6`

From the venv you can also run the GUI
`python3 app.py`

# Quirks
In room 4 at least, the actor locations seem slightly shifted on y. It seems like -100 px is the top of the screen and 380
is the bottom. So whatever the actor y is in game, we subtract 100 from it.