import pandas as pd


def Import(file_name, type):
    # type 0: week
    # type 1: weekend
    col_list = [0, 1] + list(range(4, 100))
    station_counts = pd.read_excel(
        file_name, sheetname=1, header=6, parsecols=col_list, skip_footer=2)
    del station_counts['Date'], station_counts['Note'], station_counts['nlc']
    if type == 0:
        station_counts.drop(
            station_counts.columns[[97, 98, 99, 100, 101, 102, 103]], axis=1, inplace=True)
    elif type == 1:
        station_counts.drop(
            station_counts.columns[[97, 98]], axis=1, inplace=True)
    i_rng = pd.date_range(
        '2015-01-01', '2015-01-01 23:45:00', freq='15min').time
    cols = station_counts.columns.tolist()
    cols = cols[0:1] + cols[-8:] + cols[1:89]
    station_counts = station_counts[cols]
    station_counts.set_index(['Station'], inplace=True)
    station_counts = station_counts.swapaxes(0, 1)
    station_counts.set_index(i_rng, inplace=True)
    return station_counts

if __name__ == '__main__':
    # week
    WkEntries = Import('En 12Week.xls', 0)
    WkEntries.to_csv(path_or_buf='WkEntries.csv')
    WkExits = Import('Ex 12Week.xls', 0)
    WkExits.to_csv(path_or_buf='WkExits.csv')
    # Weekend
    SatEntries = Import('En12sat.xls', 1)
    SatEntries.to_csv(path_or_buf='SatEntries.csv')
    SatExits = Import('Ex12sat.xls', 1)
    SatExits.to_csv(path_or_buf='SatExits.csv')
    SunEntries = Import('En12sun.xls', 1)
    SunEntries.to_csv(path_or_buf='SunEntries.csv')
    SunExits = Import('Ex12sun.xls', 1)
    SunExits.to_csv(path_or_buf='SunExits.csv')
