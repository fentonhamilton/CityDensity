import pandas as pd
from lxml import objectify
import math

i_rng = pd.date_range('2015-01-01', '2015-01-01 23:45:00', freq='15min').time
addressbook = pd.read_csv("Bike_Stations.csv")
distances = pd.read_csv("Bike_Station_Distances.csv", index_col=0)


class MonthFile(object):

    """Class to import monthly cycle data"""
    # Initialise and set index length of dataframe

    def __init__(self, file_name):
        self.df = pd.read_csv(file_name, parse_dates=[1, 3], dayfirst=True,
                              usecols=[1, 3, 4, 6, 7], na_values=0,
                              names=['Duration', 'e_date', 'e_id', 's_date', 's_id'],
                              header=None, skiprows=1).dropna()
        self.df.Duration = self.df.Duration.astype(int)
        # Obtain Features on initialisation
        # self.w_entries, self.w_exits, self.w_total = self.ExtractData(0)
        # self.sat_entries, self.sat_exits, self.sat_total = self.ExtractData(1)
        # self.sun_entries, self.sun_exits, self.ssun_total = self.ExtractData(2)

        # Function to write to Database
    def CalcSpeed(self):
        self.df.Duration = self.df.Duration.astype(float)
        self.df.e_id = self.df.e_id.astype(int)
        speed = pd.Series()
        for x in self.df.index:
            row_index = self.df.iloc[x, 0] - 1
            column_index = self.df.iloc[x, 2] - 1
            distance = distances.iloc[row_index, column_index]
            av_speed = distance / self.df.iloc[x, 4]
            speed = speed.append(pd.Series([av_speed]))
        speed.reset_index(drop=True, inplace=True)
        self.df['speed'] = speed

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


def GetAddressBook(file_name):
    parsed = objectify.parse(open(file_name))
    root = parsed.getroot()
    data = []
    skip_fields = ['terminalName', 'installed', 'locked', 'installDate',
                   'removalDate', 'temporary', 'nbBikes', 'nbEmptyDocks', 'nbDocks']
    for elt in root.station:
        el_data = {}
        for child in elt.getchildren():
            if child.tag in skip_fields:
                continue
            el_data[child.tag] = child.pyval
        data.append(el_data)
    addressbook = pd.DataFrame(data)
    if(len(addressbook) > 0):
        distances = pd.DataFrame(
            index=pd.Series(range(1, 781)), columns=pd.Series(range(1, 781)))
        for i in range(1, 781):
            srow_index = addressbook['id'] == i
            start = addressbook.loc[srow_index, ['id', 'lat', 'long']]
            if(len(start) > 0):
                for j in range(1, 781):
                    if i != j:
                        erow_index = addressbook['id'] == j
                        end = addressbook.loc[
                            erow_index, ['id', 'lat', 'long']]
                        if(len(end) > 0):
                            delta_lat = (
                                end.iloc[0, 1] - start.iloc[0, 1]) * math.pi / 180
                            delta_long = (
                                end.iloc[0, 2] - start.iloc[0, 2]) * math.pi / 180
                            a = math.sin(delta_lat / 2)**2 + math.cos(start.lat * math.pi / 180) * math.cos(
                                end.lat * math.pi / 180) * math.sin(delta_long / 2)**2
                            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
                            distances[j][i] = 6371000 * c
    # Output new directorys in CSV format
    addressbook.to_csv(path_or_buf='Bike_Stations.csv', columns=[
                       'long', 'lat', 'id', 'name'], index=False)
    distances.to_csv(path_or_buf='Bike_Station_Distances.csv')
    return addressbook, distances
