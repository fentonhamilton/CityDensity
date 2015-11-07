import pandas as pd
import numpy as np

# This is necessary to show lots of columns in pandas 0.12.
# Not necessary in pandas 0.13.

i_rng = pd.date_range(
    '2015-01-01', '2015-01-01 23:45:00', freq='15min').time


class MonthFile(object):

    """Class to import monthly cycle data"""
    # Initialise and set index length of dataframe

    def __init__(self, file_name):
        self.df = pd.read_csv(
            file_name,
            parse_dates=['Start Date', 'End Date'], dayfirst=True)
        # Remove entries with negative durations
        self.df = self.df.where(self.df > 0).dropna()

    def TopStations(self, start, end, x):
        self.start5 = self.df[
            'StartStation Id'].value_counts()[:x].index.tolist()
        self.end5 = self.df['EndStation Id'].value_counts()[:x].index.tolist()
        if start and end is True:
            return self.start5, self.end5
        elif start is True:
            return self.start5
        elif end is True:
            return self.end5

    def ExtractData(self, weektime):
        # weektime 1:weekday, 2:saturday, 3:sunday
        self.icount = pd.DataFrame(index=i_rng)
        self.counts = self.df[
            ['Start Date', 'StartStation Id', 'EndStation Id', 'End Date']]
        self.counts = self.counts.rename(
            columns={'Start Date': 's_date', 'StartStation Id': 's_id',
                     'End Date': 'e_date', 'EndStation Id': 'e_id'})
        self.counts['weekday'] = self.counts[
            's_date'].apply(lambda x: x.weekday())

        if weektime == 0:
            self.w_time = self.counts['weekday'] < 5
        if weektime == 1:
            self.w_time = self.counts['weekday'] == 5
        if weektime == 2:
            self.w_time = self.counts['weekday'] == 6

        self.counts = self.counts.loc[
            self.w_time, ['s_date', 's_id', 'e_date' 'weekday']]
        self.days = len(
            self.counts['s_date'].apply(lambda t: t.date()).unique())

        for i in range(1, 750):
            row_index = self.counts['s_id'] == i
            self.d_counts = self.counts.loc[row_index, ['s_date', 's_id']]
            if(len(self.d_counts) > 0):
                self.d_counts['s_id'] = self.d_counts.loc[
                    :, ('s_id')].dropna().map(lambda x: 1)
                self.d_counts = self.d_counts.set_index(
                    self.d_counts['s_date'])
                group = self.d_counts.groupby(
                    pd.TimeGrouper(freq='15Min', nperiods=96)).sum()
                group['time'] = group.index.time
                group = group.rename(columns={'s_id': 'entries'})
                self.icount[i] = pd.pivot_table(
                    group, values=['entries'], index=['time'], aggfunc=np.sum)

        self.icount = self.icount.applymap(lambda x: x / self.days).fillna(0)
        return self.icount
