# Telegram bot fetching USD currency exchange rate from MOEX

Currently designed to work on Heroku cloud.

## How to start

Update Telegram bot token and server hostname:

`heroku config:set TELEGRAM_API_TOKEN=<your_token_here>`

`heroku config:set WEBHOOK_HOSTNAME=<heroku_app_hostname>`

And then `git push heroku master` to run your app.
