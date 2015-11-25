# The usual preamble
# %matplotlib inline
import pandas as pd
import matplotlib.pyplot as plt
from itertools import groupby
from datetime import datetime, timedelta

pd.set_option('display.mpl_style', 'default')  # Make the graphs a bit prettier
plt.rcParams['figure.figsize'] = (15, 5)
# This is necessary to show lots of columns in pandas 0.12.
# Not necessary in pandas 0.13.
pd.set_option('display.width', 5000)
pd.set_option('display.max_columns', 60)
raw_df = pd.read_csv(
    "FullTest.csv", parse_dates=['Start Date', 'End Date'], dayfirst=True)
raw_df[:20]  # Show first 20
# Count of most used stations
station_counts = raw_df['StartStation Name'].value_counts()
station_counts[:10].plot(kind='bar')  # need to include end points

StationCount = raw_df[['Start Date', 'StartStation Name', 'StartStation Id']]
StationCount = StationCount.rename(
    columns={'Start Date': 'start_date', 'StartStation Name': 'start_station',
             'StartStation Id': 'start_station_id'})
StationCount[:20]
# Seperate out weekdays and find number of weekdays within the dataframe
StationCount['weekday'] = StationCount[
    'start_date'].apply(lambda x: x.weekday())
StationCount['time'] = StationCount['start_date'].apply(lambda x: x.time())
mon_fri = StationCount['weekday'] < 5
weekday = StationCount.loc[
    mon_fri, ['start_date', 'start_station_id', 'time', 'weekday']]
unique_days = len(weekday['start_date'].map(lambda t: t.date()).unique())
# Approximate number of stations (find max value from column?)
i = 311
# for i in range(0, 750):
# Need to Divide into days of the week, sat, sun first. Easier to average
row_index = StationCount['start_station_id'] == i
IDcount = StationCount.loc[row_index, ['start_date', 'start_station_id']]
IDcount['start_station_id'] = IDcount.loc[
    :, ('start_station_id')].dropna().map(lambda x: 1)
IDcount['start_date'] = IDcount['start_date'].apply(
    lambda x: x.strftime('%H:%M:%S'))
IDcount['start_date'] = pd.to_datetime(IDcount['start_date'])
IDcount = IDcount.set_index(['start_date'])

grouper = IDcount.groupby(pd.TimeGrouper(freq='15Min', nperiods=96)).sum()
# time_df = IDcount.groupby(times.minute).sum().reset_index()
# time_df = IDcount.groupby(15*times.minute).sum().reset_index()
grouper
