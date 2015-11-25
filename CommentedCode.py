# mod_df = raw_df.where(raw_df > 0) 
# t_format = '%H:%M:%S'
# t2_format = '%d/%m/%Y %H:%M:%S'
# StationCount['time'] = StationCount['start_date'].apply(lambda x: x.time())
# StationCount['time'] = StationCount['time'].apply(lambda x: datetime.strptime(x, t_format))
# StationCount['time'] = StationCount.start_date.map(lambda x: pd.datetools.parse(x).time())

# StationCount['time'] = StationCount['start_date'].apply(lambda x: datetime.strptime(x, t_format).time())
# IDcount = pd.data_range('00:00', '00:00', freq='15Min')
# IDcount.time = pd.to_datetime(IDcount['time'])
# j = 0
# a = datetime.time()
# b = datetime.time(minute=15)
# test = IDcount.ix[IDcount.index.indexer_between_time(a, b)]
# test

# IDcount = IDcount.resample('15Min', fill_method='pad', how='sum')

# IDcount.head()

# result = IDcount['time'].value_counts()
# IDcount['time'] = pd.to_datetime(IDcount['time'])
# IDcount
# IDcount = IDcount.set_index(['time'])


# time_df = IDcount.groupby(times.minute).sum().reset_index()
# time_df = IDcount.groupby(15*minute).sum().reset_index()


row_index = weekday['start_station_id'] == i
IDcount = weekday.loc[row_index, ['start_date', 'time', 'start_station_id', ]]
IDcount['start_station_id'] = IDcount.loc[:,('start_station_id')].dropna().map(lambda x: 1)

IDcount = IDcount.set_index(IDcount['start_date'])

grouper = IDcount.groupby(pd.TimeGrouper(freq='15Min', nperiods=96)).sum()
grouper['time'] = grouper.index.time
grouper = grouper.rename(columns={'start_station_id': 'entries'})

icount[i] = pd.pivot_table(grouper, values=['entries'], index=['time'], aggfunc=np.sum )
# icount = result.rename(columns={'entries': i})
icount