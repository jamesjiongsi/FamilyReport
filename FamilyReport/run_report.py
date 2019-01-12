# -*- coding: utf-8 -*-
import sys
import smtplib
from datetime import datetime
from datetime import date
from dateutil import tz
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
import pandas as pd
import numpy as np
from data import conf
import requests

def days_between(d1, d2):
    d1 = datetime.strptime(d1, "%Y-%m-%d")
    d2 = datetime.strptime(d2, "%Y-%m-%d")
    return abs((d2 - d1).days)

def utc_to_est(utc_timestamp):
    from_zone = tz.gettz('UTC')
    to_zone = tz.gettz('EST')
    utc_time = datetime.fromtimestamp(utc_timestamp)
    utc_time = utc_time.replace(tzinfo=from_zone)
    local_time = utc_time.astimezone(to_zone)
    return local_time.strftime('%Y-%m-%d %H:%M:%S')

def ord(n):
    return str(n)+("th" if 4 <= n%100 <= 20 else {1:"st",2:"nd",3:"rd"}.get(n%10, "th"))

def summarize_weather(list_weather):
    weather_cnt = dict()
    for value in list_weather:
        cnt = weather_cnt.get(value, 0)
        cnt += 1
        weather_cnt[value] = cnt
    max_cnt = -1
    weather_summary = ''
    for v in weather_cnt:
        if weather_cnt[v] > max_cnt:
            max_cnt = weather_cnt[v]
            weather_summary = v
    return weather_summary

class FamilyReport(object):

    def __init__(self):
        pass

    def generate_email(self):
        pass

    def get_weather(self):
        payload = {'id': conf.city_id,
                   'appid': conf.weather_app_id,
                   'units': 'metric',
        }
        weather_url = 'http://api.openweathermap.org/data/2.5/forecast?'
        weather_response = requests.get(weather_url, params=payload)
        weather_response.raise_for_status() # If not 200, raise exception
        res = weather_response.json()
        weather_of_date = dict()
        for item in res['list']:
            str_time = utc_to_est(item['dt'])
            date_forcasted = str_time.split(" ")[0]
            temp = round(item['main']['temp'], 1)
            weather = item['weather'][0]['main'] + " (" + item['weather'][0]['description'] + ")"
            if date_forcasted not in weather_of_date:
                weather_of_date[date_forcasted] = {'min_temp': temp,
                                                   'max_temp': temp,
                                                   'weather': [weather]}
            else:
                weather_of_date[date_forcasted]['min_temp'] = min(temp,
                                                                  weather_of_date[date_forcasted]['min_temp'])
                weather_of_date[date_forcasted]['max_temp'] = max(temp,
                                                                  weather_of_date[date_forcasted]['max_temp'])
                weather_of_date[date_forcasted]['weather'].append(weather)
        for k, v in weather_of_date.items():
            v['weather'] = summarize_weather(v['weather'])
        sorted_weather = sorted(weather_of_date.items(), key=lambda x: x[0])
        return sorted_weather

    def send_email(self):

        # Date information
        date_of_landing='2018-11-12'
        date_of_today = date.today().strftime("%Y-%m-%d")
        day_of_year = date.today().strftime("%j")
        day_of_week = date.today().strftime("%A")
        # week_of_year = date.today().strftime("%W")
        percent = round((float(day_of_year) + 0.0) / 3.65, 1)
        progress_bar = str(percent) + '% |' + round(percent) * '#' + (100 - int(percent)) * '-' + '|'

        # Weather
        list_weather = self.get_weather()
        str_forecast = ''
        for idx, item in enumerate(list_weather):
            str_forecast += ("<tr style=\"background-color: #dddddd\">" if (idx % 2 == 0) else "<tr>") + \
                   "<th>" + item[0] + \
                   "</th><th>" + str(item[1]['min_temp']) + \
                   "</th><th>" + str(item[1]['max_temp']) + \
                   "</th><th>" + item[1]['weather'] + "</th></tr>\n"

        style = """
        <style>
        table {
        font-family: arial, sans-serif;
        border-collapse: collapse;
        width: 60%;
        }
        td, th {
        border: 1px solid #dddddd;
        text-align: right;
        padding: 8px;
        }
        tr:nth-child(even) {
            background-color: #dddd11;
        }
        </style>
        """
        weather_info = '''
        <h2>Weather information</h2>
        <table>
        <caption>Weather forecast of the following 5 days</caption>
        <tr><th>Date</th><th>Min Temp.</th><th>Max Temp.</th><th>Weather</th></tr>
        {forecast}
        </table>
        '''.format(forecast=str_forecast)
        # Food expenses
        df = pd.read_csv(conf.data_path + '/' + 'food_expense', sep='\t')
        cost = round(df['Expense'].sum(), 2)
        days_since_landing = days_between(date_of_landing, date_of_today)
        mail_msg = """
        <!DOCTYPE html>
        <html>
        <head>
        {style}
        </head>
        <body>
        <h2>Date information</h2>
        <p>Today is <b>{date}</b>, <b>{week}</b>, the {doy} day in this year.</p>
        <p>This year's progress is as follows: </p>
        <p>{progress}</p>
        <hr />
        {weather_info}
        <hr />
        <h2>Expenses on food</h2>
        <p>We've landed in Toronto for {dsl} days, and spent ${cost} on food.</p>
        <p>Our average daily expense on food is: <b> ${cpd} / d </b>.</p>
        <hr />
        <h4>This is an automatically generated email, however, you can reply if you insist. To unsubscribe, please discuss with your husband in person.</h4>
        --------------
        <h4>Have a nice day!</h4>
        </body>
        </html>
        """.format(date=date_of_today, week=day_of_week, doy=ord(int(day_of_year)),
                   weather_info=weather_info,style=style,
                   progress=progress_bar, dsl=days_since_landing, cost=cost, cpd=round(float(cost)/days_since_landing, 2))
        message = MIMEText(mail_msg, 'html', 'utf-8')
        message['From'] = Header("Bo Pang", 'utf-8')
        # message['To'] = Header("Ms. Egg", 'utf-8')
        subject = 'FAMILY REPORT @ {}'.format(date_of_today)
        message['Subject'] = Header(subject, 'utf-8')
        try:
            print("connect ...")
            server = smtplib.SMTP('{host}:{port}'.format(host=conf.mail_host, port=conf.mail_port))
            server.ehlo()
            server.starttls()
            print("login ...")
            server.login(conf.sender, conf.mail_pswd)
            print("send ...")
            server.sendmail(conf.sender, conf.receivers, message.as_string())
            server.quit()
            print("Successfully sent email.")
        except smtplib.SMTPException as e:
            print(e)

    def run(self):
        self.send_email()

if __name__ == '__main__':
    # main process
    family_report = FamilyReport()
    family_report.run()
