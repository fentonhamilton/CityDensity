import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# matplotlib
%matplotlib inline
pd.set_option('display.width', 5000)
pd.set_option('display.max_columns', 60)
pd.set_option('display.mpl_style', 'default')

i_rng = pd.date_range('2015-01-01', '2015-01-01 23:45:00', freq='15min').time
df = pd.read_csv('fulltest.csv', parse_dates=[1,3], dayfirst=True, usecols=[1,3,4,6,7], na_values=0, names=['Duration', 'e_date', 'e_id', 's_date', 's_id'], header=False).dropna()
top5 = df.s_id.value_counts()[:3].index.tolist()

icount = pd.DataFrame(index=i_rng, columns=range(1,781))
jcount = pd.DataFrame(index=i_rng, columns=range(1,781))
sdays = len(df['s_date'].apply(lambda t: t.date()).unique())
edays = len(df['e_date'].apply(lambda t: t.date()).unique())

for i in range(1, 780):
    sw_time = df.s_date.apply(lambda x: x.weekday() < 5) & (df.s_id == i)
    ew_time = df.e_date.apply(lambda x: x.weekday() < 5) & (df.e_id == i)
    s_counts = df.loc[sw_time, ['s_id', 's_date']]
    e_counts = df.loc[ew_time, ['e_date', 'e_id']]
    s_counts.set_index(s_counts['s_date'], inplace=True)
    e_counts.set_index(e_counts['e_date'], inplace=True)
    if(len(s_counts) > 0):
        s_counts['s_id'] = s_counts.loc[:, ('s_id')].dropna().map(lambda x: 1)
        s_counts = s_counts.set_index(s_counts['s_date'])
        group = s_counts.groupby(pd.TimeGrouper(freq='15Min', nperiods=96)).sum()
        group['time'] = group.index.time
        group = group.rename(columns={'s_id': 'entries'})
        icount[i] = pd.pivot_table(group, values=['entries'], index=['time'], aggfunc=np.sum)
    if(len(e_counts) > 0):
        e_counts['e_id'] = e_counts.loc[:, ('e_id')].dropna().map(lambda x: 1)
        e_counts = e_counts.set_index(e_counts['e_date'])
        group2 = e_counts.groupby(pd.TimeGrouper(freq='15Min', nperiods=96)).sum()
        group2['time'] = group2.index.time
        group2 = group2.rename(columns={'e_id': 'entries'})
        jcount[i] = pd.pivot_table(group2, values=['entries'], index=['time'], aggfunc=np.sum)

        

# icount.entries = icount.entries.applymap(lambda x: x / sdays).fillna(0)
# icount.exits = icount.exits.applymap(lambda x: x / edays).fillna(0)

jcount = jcount.dropna(how='all', axis=1).applymap(lambda x: x / edays).fillna(0)
icount = icount.dropna(how='all', axis=1).applymap(lambda x: x / sdays).fillna(0)
total = pd.concat([icount, jcount], axis=1, keys=['Entries', 'Exits'])
# total = total.unstack()
# total = total.stack(level=['Entries', 'Exits'])
total = total.swaplevel(0, 1, axis=1).reindex_axis(range(1,781), axis=1, level=0)
total