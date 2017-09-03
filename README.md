# data-combine ![logo](datacombine/datacombine/static/pictures/data_combine_logo_smaller.png)

The data management solution for the Youth and Young Adult Network of the
National Farmworker Ministry in Orlando; which is the best, most lit, most
radical of all the YAYA's.

## Version 0.1: Codename "Beautiful Backend"

What Data-Combine is now (starting from the bottom):

    * A bash script to setup a postgres server on Linux. We're working on a
    Docker container for those weirdos not using Linux.
    * Mine High-Rise text files for Contacts.
    * There is a very minimal Django server with very basic user functionality. 
    * Harvest Contstant Contact Lists and Contacts through Constant Contacts API.
    * Create a local postgres SQL database with Django ORM.
    * Update local database from ConstantContact.

The most obvious next step is the ability to update ConstantContact from a local 
database. Also there needs to be a lot of improvement on the actual views, which
largely don't exist. Other things we'd like in the very near future:

    * The DataCombine saves a list of phone numbers and other fields that need
    to be corrected. The goal is to have a view which could guide a user to fix
    these errors and then submit them locally and to the ConstantContact db.
    * A view to print out and share call lists based on certain criteria.
    * Views to manage ConstantContact contacts and lists on local db and on
    ConstantContact's db.
    * Make things more pretty to look at.

## How do I use this? Can I use this? Should I use this?

Read on / Maybe, I don't know what you can do. / I don't know who you are, 
maybe?

### Installing DataCombine

You need to have Python 3.6 installed (and pip). I assume you know how to do this, 
because you're on github, but if you need help talk to Thomas, or Google. You
should know one of these two things. You'll also need a postgres SQL server
installed. There is a bash script to do this (ie. 'db_setup.sh'). This will not 
work outside of a Ubuntu / (maybe) Debian OS. Again, reference Thomas or Google.

(**Note not all Thomas's ('Thomasi'?, 'Thomases'?, WHATEVER THE PLURAL FORM OF 
MY NAME IS) are Thomas. Consult your local Thomas for more.)

It's recommended that you setup a Python virtual environment. If you have git 
installed, and you should. Once you've activated the virtual environment, and 
are in the directory you want to establish do the following (in the commandline,
like an adult):

```
git clone https://github.com/Crimson-Star-Software/data-combine.git
pip install -r datacombine/datacombine/requirements.txt # This will download all the python libraries you need
```

Now you're mostly there. The only thing you need now is a 'secret_settings.py'
file which contain your ConstantContact `API_KEY`, `AUTH_KEY` and the 
`POSTGRES_PASSWORD` of your local postgres SQL database for this application. 
Obviously this is not something that should be in your git repo, which is exactly
why this file is in the `.gitignore` file. Either ask Thomas for a copy, or make
your own, for your own ConstantContact account and local Postgres SQL db.

### Using DataCombine

Much of the functonality is standard Django fare, through the standard manage.py
script. I'm not going over that here, as Django is very well documented online.

#### Setting up your local database from constant contact

Run the following using the IPython shell provided by Django:

To launch the shell, from the directory manage.py is in: `python manage.py shell`

```python
from datacombine.data_combine import DataCombine
from datacombine.models import (
    Contact,
    Phone,
    EmailAddress,
    ConstantContactList,
    Note,
    Address,
    UserStatusOnCCList
)
import logging
# Choose your logging level, the output will be in 
# datacombine/datacombine/logs/dcombine.log, in a rotating file; if you don't like this
# code a replacement.
# logging.DEBUG <- ALL THE MESSAGES
# logging.INFO <- Messages to inform
# logging.WARNING <- Only the messages that are bad
# logging.ERROR <- Only the messages that'll probably crash the program 
dc = DataCombine(loglvl=logging.DEBUG)
dc.combine_and_update_new_entries()
```

That **should** do it. Probably. Maybe.