import pandas as pd

i_rng = pd.date_range('2015-01-01', '2015-01-01 23:45:00', freq='15min').time


class MonthFile(object):

    """Class to import monthly cycle data"""
    # Initialise and set index length of dataframe

    def __init__(self, file_name):
        self.df = pd.read_csv(file_name, parse_dates=[1, 3], dayfirst=True,
                              usecols=[1, 3, 4, 6, 7], na_values=0,
                              names=[
                                  'Duration', 'e_date', 'e_id', 's_date', 's_id'],
                              header=False).dropna()
        # self.w_entries, self.w_exits, self.w_total = self.ExtractData(0)
        # self.sat_entries, self.sat_exits, self.sat_total = self.ExtractData(1)
        # self.sun_entries, self.sun_exits, self.ssun_total = self.ExtractData(2)

        # Function to write to Database

    def TopStations(self, start, end, x):
        self.start5 = self.df.s_id.value_counts()[:x].index.tolist()
        self.end5 = self.df.e_id.value_counts()[:x].index.tolist()
        if start and end is True:
            return self.start5, self.end5
        elif start is True:
            return self.start5
        elif end is True:
            return self.end5

    def ExtractData(self, weektime):
        icount = pd.DataFrame(index=i_rng, columns=range(1, 781))
        jcount = pd.DataFrame(index=i_rng, columns=range(1, 781))
        if weektime != 3:
            if weektime == 0:
                sw_time = self.df.s_date.apply(lambda x: x.weekday() < 5)
                ew_time = self.df.e_date.apply(lambda x: x.weekday() < 5)
            if weektime == 1:
                sw_time = self.df.s_date.apply(lambda x: x.weekday() == 5)
                ew_time = self.df.e_date.apply(lambda x: x.weekday() == 5)
            if weektime == 2:
                sw_time = self.df.s_date.apply(lambda x: x.weekday() == 6)
                ew_time = self.df.e_date.apply(lambda x: x.weekday() == 6)
            s_counts = self.df.loc[sw_time, ['s_id', 's_date']]
            e_counts = self.df.loc[ew_time, ['e_date', 'e_id']]
            sdays = len(s_counts['s_date'].apply(lambda t: t.date()).unique())
            edays = len(e_counts['e_date'].apply(lambda t: t.date()).unique())
        else:
            s_counts = self.df[['s_id', 's_date']]
            e_counts = self.df[['e_date', 'e_id']]
            sdays = len(s_counts['s_date'].apply(lambda t: t.date()).unique())
            edays = len(e_counts['e_date'].apply(lambda t: t.date()).unique())
        for i in range(1, 781):
            i_start = s_counts.s_id == i
            i_end = e_counts.e_id == i
            s1_counts = s_counts.loc[i_start, ['s_id', 's_date']]
            e1_counts = e_counts.loc[i_end, ['e_date', 'e_id']]
            if(len(s1_counts) > 0):
                s1_counts.set_index(['s_date'], inplace=True)
                group = s1_counts.groupby(
                    pd.TimeGrouper(freq='15Min', nperiods=96)).sum()
                group.set_index(group.index.time, inplace=True)
                icount[i] = group.groupby(group.index).sum()
                icount[i] = icount[i].apply(lambda y: y / i)
            if(len(e1_counts) > 0):
                e1_counts.set_index(['e_date'], inplace=True)
                group2 = e1_counts.groupby(
                    pd.TimeGrouper(freq='15Min', nperiods=96)).sum()
                group2.set_index(group2.index.time, inplace=True)
                jcount[i] = group2.groupby(group2.index).sum()
                jcount[i] = jcount[i].apply(lambda y: y / i)
        entries = icount.dropna(how='all', axis=1).applymap(
            lambda x: x / sdays).fillna(0)
        exits = jcount.dropna(how='all', axis=1).applymap(
            lambda x: x / edays).fillna(0)
        total = pd.concat([entries, exits], axis=1, keys=['Entries', 'Exits'])
        total = total.swaplevel(0, 1, axis=1).reindex_axis(
            range(1, 781), axis=1, level=0)
        return entries, exits, total
