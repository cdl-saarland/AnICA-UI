TODO write this

### Installation


### Running the UI
The django test server can be started using the following command:
```
./manage.py runserver 8000
```
With this command running on a system, the UI will be available on that system
in a web browser (tested mainly with Chromium) at
`http://127.0.0.1:8000/devidisc/`.


### Adding New Campaigns

New devidisc campaigns can be added to the UI via a [management command](https://docs.djangoproject.com/en/3.2/howto/custom-management-commands/):
```
./manage.py import_campaigns path/to/first/campaign/dir path/to/second/campaign/dir ...
```

