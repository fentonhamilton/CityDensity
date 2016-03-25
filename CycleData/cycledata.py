import pandas as pd
from lxml import html
import math
import os
import shutil
import requests
import zipfile
import numpy as np
from PyQt4.QtGui import *
from PyQt4.QtCore import *
from PyQt4.QtWebKit import *
import sys
from collections import OrderedDict

i_rng = pd.date_range('2015-01-01', '2015-01-01 23:45:00', freq='15min').time
wd = str(os.getcwd())
years = ['2012', '2013', '2014', '2015', '2016']
# addressbook = pd.read_csv("Bike_Stations.csv")
# distances = pd.read_csv("Bike_Station_Distances.csv", index_col=0)


class Render(QWebPage):
    # Render class courtesy of
    # https://impythonist.wordpress.com/2015/01/06/ultimate-guide-for-scraping-javascript-rendered-web-pages/
    def __init__(self, url):
        self.app = QApplication(sys.argv)
        QWebPage.__init__(self)
        self.loadFinished.connect(self._loadFinished)
        self.mainFrame().load(QUrl(url))
        self.app.exec_()

    def _loadFinished(self, result):
        self.frame = self.mainFrame()
        self.app.quit()


class Model(object):
    """Class for modelling a stations behaviour"""

    def __init__(self, dataframe, station_id):
        super(Model, self).__init__()
        self.ID = station_id
        self.DF = self.FilterStation(dataframe)
        self.WD = pd.DataFrame()
        self.WE = pd.DataFrame()

    def FilterStation(self, dataframe):
        row_index = (dataframe.s_id == self.ID) | (dataframe.e_id == self.ID)
        StationFrame = dataframe.loc[
            row_index, ['e_date', 'e_id', 's_date', 's_id']]
        return StationFrame

    def FormatEntries(self):
        entry_index = self.DF.s_id == self.ID
        dataframeE = self.DF.loc[entry_index, ['s_id', 's_date']]
        dataframeE.set_index('s_date', inplace=True)
        dataframeE = dataframeE.resample("30Min", how=self.custom_resampler, fill_method='pad')
        del dataframeE.index.name
        return dataframeE

    def FormatExits(self):
        exit_index = self.DF.e_id == self.ID
        dataframeEx = self.DF.loc[exit_index, ['e_date', 'e_id']]
        dataframeEx.set_index('e_date', inplace=True)
        dataframeEx = dataframeEx.resample("30Min", how=self.custom_resampler, fill_method='pad')
        del dataframeEx.index.name
        return dataframeEx

    def custom_resampler(self, array_like):
        return np.sum(array_like) / self.ID

    def f(self, x):
        return x[0] - x[1]

    def CalcDiff(self, dataframeE, dataframeEx):
        dataframe = pd.concat([dataframeE, dataframeEx], axis=1)
        dataframe.fillna(value=0, inplace=True)
        dataframe['count_diff'] = dataframe.apply(self.f, axis=1)
        return dataframe

    def PreProcess(self):
        # Filter to specific station
        fullE = self.FormatEntries()
        fullEx = self.FormatExits()
        # Seperate week
        WDentry, WEentry = SeperateWeek(fullE, index=True)
        WDexit, WEexit = SeperateWeek(fullEx, index=True)
        # Calculate entry/exit differences
        WDdiff = self.CalcDiff(WDentry, WDexit)
        WEdiff = self.CalcDiff(WEentry, WEexit)
        # Format resultant dataframes
        self.WD = WDdiff.drop(['s_id', 'e_id'], axis=1)
        self.WE = WEdiff.drop(['s_id', 'e_id'], axis=1)
        self.WD.count_diff = self.WD.count_diff.astype(int)
        self.WD.count_diff = self.WD.count_diff.apply(lambda x: x + 300)
        self.WE.count_diff = self.WE.count_diff.astype(int)
        self.WE.count_diff = self.WE.count_diff.apply(lambda x: x + 300)


def GetAddressBook():
    url = 'https://api.tfl.gov.uk/bikepoint'
    resp = requests.get(url)
    Jfile = resp.json()
    ab = []
    for i in Jfile:
        ab.append(
            {'long': i["lon"], 'lat': i["lat"], 'id': i["id"][11:], 'name': i["commonName"]})
    addressbook = pd.DataFrame(ab)
    addressbook.id = addressbook.id.astype(int)
    addressbook.sort_values(by='id', axis=0, ascending=True, inplace=True)
    addressbook.set_index(addressbook.id, inplace=True, drop=True)
    # Find stations not listed in addressbook
    add = pd.DataFrame(index=pd.Series(range(1, max(addressbook.id) + 1)))
    DF = add.join(addressbook)
    missingStations = DF[DF.isnull().any(axis=1)].index
    addressbook.to_csv(path_or_buf='Bike_Stations.csv', columns=[
                       'long', 'lat', 'id', 'name'], index=False)
    return addressbook, missingStations


def GetDistances(addressbook):
    # Compute distance between stations
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
    distances.to_csv(path_or_buf='Bike_Station_Distances.csv')
    return distances


def SeperateWeek(dataframe, index=False):
    if(index is True):
        w_indexer = dataframe.index.weekday < 5
        we_indexer = dataframe.index.weekday > 4
    else:
        w_indexer = dataframe.s_date.apply(lambda x: x.weekday() < 5)
        we_indexer = dataframe.s_date.apply(lambda x: x.weekday() > 4)
    Week = dataframe.loc[w_indexer, :]
    WeekEnd = dataframe.loc[we_indexer, :]
    Week.reset_index(inplace=True, drop=True)
    WeekEnd.reset_index(inplace=True, drop=True)
    print('Weekdays and Weekends seperated')
    return Week, WeekEnd


def DayAverage(dataframe):
    dataframe["Count"] = 1
    Days = dataframe.set_index('s_date')
    # Resample to 1 Day
    Days.drop(['s_id', 'e_id', 'e_date', 'Duration'], axis=1, inplace=True)
    Days = Days.resample('1D', how='sum')
    return Days


def GetURLs():
    url = 'http://cycling.data.tfl.gov.uk/'
    r = Render(url)
    result = r.frame.toHtml()
    # QString should be converted to string before processed by lxml
    formatted_result = str(result)
    # Next build lxml tree from formatted_result
    tree = html.fromstring(formatted_result)
    # Now using correct Xpath we are fetching URL of archives
    # archive_links[2:18]
    URLs = tree.xpath('//@href')
    links = []
    for url in URLs:
        if((url[-3:] == 'csv') or (url[-3:] == 'zip')):
            links.append(url)
    print('Acquired URLs')
    return links


def DownloadFiles():
    urls = GetURLs()
    new_path = wd + '\RawData'
    os.chdir(new_path)
    URLs = []
    res = []
    for url in urls:
        name = url[43:]
        filename = os.path.join(new_path, name)
        if not os.path.isfile(filename):
            URLs.append(url)
    for x in URLs:
        print('Downloading: ' + x)
        res = requests.get(x)
        res.raise_for_status()
        with open(str(x[43:]), "wb") as file:
            file.write(res.content)
    print('Downloads completed')


def ExtractFiles():
    directory = wd + '\RawData'
    # Read all filenames and extract
    file_names = []
    for filename in os.listdir(directory):
        if(filename[-4:] == '.zip'):
            new_path = directory + '\\' + filename[-8:-4]
            if not os.path.exists(new_path):
                os.mkdir(new_path)
            try:
                os.chdir(directory)
                print('Extracting: ' + filename)
                testZip = zipfile.ZipFile(filename)
                file_names.append(testZip.namelist())
                testZip.extractall(new_path)
                testZip.close()
            except:
                print('Already Extracted: ' + filename)


def OrganizeFiles():
    path = wd + '\RawData'
    preSize = {}
    postSize = {}
    updated = {}
    for year in years:
        updated[year] = False
    for filename in os.listdir(path):
        if(filename[-3:] == 'csv'):
            for year in years:
                if(filename[-6:-4] == year[-2:]):
                    cfile = path + '\\' + year + '\\' + filename
                    if not os.path.exists(path + '\\' + year):
                        os.mkdir(path + '\\' + year)
                    preSize[year] = len(os.listdir(path + '\\' + year))
            file = path + '\\' + filename
            try:
                shutil.copy(file, cfile)
            except:
                os.mkdir(path + '\\' + year)
                shutil.copy(file, cfile)
    for x in preSize:
        postSize[x] = len(os.listdir(path + '\\' + year))
        if(preSize[x] < postSize[x]):
            updated[x] = True
    return updated


def ReadFiles(directory):
    # Read all csv files within directory
    # Return dataframe of all CSVs combined
    os.chdir(directory)
    DF = pd.DataFrame()
    for filename in os.listdir(directory):
        if(filename[-4:] == '.csv'):
            print("Reading: " + filename)
            try:
                Dfile = pd.read_csv(filename, parse_dates=[1, 3], dayfirst=True, usecols=[1, 3, 4, 6, 7],
                                    na_values=[0, 'Tabletop1'], names=['Duration', 'e_date', 'e_id', 's_date', 's_id'],
                                    header=None, skiprows=1, dtype={'Duaration': np.float32, 's_id': np.float32, 'e_id': np.float32}).dropna()
            except:
                Dfile = pd.read_csv(filename, parse_dates=[1, 3], dayfirst=True, usecols=[1, 3, 4, 6, 7],
                                    na_values=[0, 'Tabletop1'], names=['Duration', 'e_date', 'e_id', 's_date', 's_id'],
                                    header=None, skiprows=1).dropna()
                Dfile = Dfile.apply(pd.to_numeric, errors='coerce').dropna()
            DF = DF.append(Dfile)
    DF.Duration = DF.Duration.astype(int)
    DF.s_id = DF.s_id.astype(int)
    DF.e_id = DF.e_id.astype(int)
    return DF


def CreateYearFrames(updatedFolder):
    filenames = ['FullYear.csv', 'Weekdays.csv', 'WeekEnds.csv']
    DF = {}
    DFweek = {}
    DFweekEnd = {}
    for year in years:
        pt_path = wd + '\Features\\' + year
        full_path = pt_path + '\\' + year
        i = 0
        for file in filenames:
            if(os.path.isfile(full_path + file)):
                i += 1
        if((i == len(filenames)) and (updatedFolder[year] is False)):
            print('Features already extracted for year: ' + year)
            continue
        DF[year] = ReadFiles(wd + '\\' + 'RawData' + '\\' + year)
        if not os.path.exists(pt_path):
            os.mkdir(pt_path)
        DFweek[year], DFweekEnd[year] = SeperateWeek(DF[year])
        print('Writing: ' + year + filenames[0])
        DF[year].to_csv(full_path + filenames[0])
        print('Writing: ' + year + filenames[1])
        DFweek[year].to_csv(full_path + filenames[1])
        print('Writing: ' + year + filenames[2])
        DFweekEnd[year].to_csv(full_path + filenames[2])
        print(year + ' YearFrame completed')
    return DFweek, DFweekEnd


def YearsDaily(Weekdays, WeekEnds):
    filenames = ['WeekDaily.csv', 'WeekEndDaily.csv']
    WeekDaily = {}
    WeekEndDaily = {}
    for year in years:
        path = wd + "\Features\\" + year
        full_path = path + '\\' + year
        i = 0
        for file in filenames:
            if(os.path.isfile(full_path + file)):
                i += 1
        if((i == len(filenames)) and (updatedFolder[year] is False)):
            print('Daily Features already extracted for year: ' + year)
            continue
        else:
            try:
                WeekDaily[year] = DayAverage(Weekdays[year])
                WeekEndDaily[year] = DayAverage(WeekEnds[year])
            except:
                continue
        if not os.path.exists(path):
            os.mkdir(path)
        print('Writing: ' + filenames[0])
        WeekDaily[year].to_csv(full_path + filenames[0])
        print('Writing: ' + filenames[1])
        WeekEndDaily[year].to_csv(full_path + filenames[1])
    return WeekDaily, WeekEndDaily


def FileStructure():
    try:
        os.mkdir(wd + "\Features")
        os.mkdir(wd + "\RawData")
    except:
        print('Directories already exist')


def Import(type):
    # type: 'daily' or 'fullyear' or 'split'
    directory = wd + '\Features\\'
    Weekdays = OrderedDict()
    WeekEnds = OrderedDict()
    FullYear = OrderedDict()
    WDdaily = OrderedDict()
    WEdaily = OrderedDict()
    for year in years:
        path = directory + year
        if(os.path.exists(path)):
            if(type == 'daily'):
                print('Reading ' + year + 'WeekDaily.csv')
                WDdaily[year] = pd.read_csv(path + '\\' + year + 'WeekDaily.csv', parse_dates=0, index_col=0,
                                            dtype={'Count': np.float32})
                print('Reading ' + year + 'WeekEndDaily.csv')
                WEdaily[year] = pd.read_csv(path + '\\' + year + 'WeekEndDaily.csv', parse_dates=0, index_col=0,
                                            dtype={'Count': np.float32})
            elif(type == 'fullyear'):
                FullYear = OrderedDict()
                print('Reading ' + year + 'FullYear.csv')
                FullYear[year] = pd.read_csv(path + '\\' + year + 'FullYear.csv', parse_dates=[2, 4], index_col=0,
                                             dtype={'Duaration': np.float32, 's_id': np.float32, 'e_id': np.float32})
            elif(type == 'split'):
                print('Reading: ' + year + 'Weekdays.csv')
                Weekdays[year] = pd.read_csv(path + '\\' + year + 'Weekdays.csv', parse_dates=[2, 4], index_col=0,
                                             dtype={'Duaration': np.float32, 's_id': np.float32, 'e_id': np.float32})
                print('Reading: ' + year + 'WeekEnds.csv')
                WeekEnds[year] = pd.read_csv(path + '\\' + year + 'WeekEnds.csv', parse_dates=[2, 4], index_col=0,
                                             dtype={'Duaration': np.float32, 's_id': np.float32, 'e_id': np.float32})
            else:
                continue
    if(type == 'daily'):
        return WDdaily, WEdaily
    elif(type == 'fullyear'):
        return FullYear
    elif(type == 'split'):
        return Weekdays, WeekEnds
    else:
        return 0


def JoinYears(WDdays, WEdays):
    WDs = pd.DataFrame()
    WEs = pd.DataFrame()
    for x in WDdays:
        WDs = WDs.append(WDdays[x])
    for y in WEdays:
        WEs = WEs.append(WEdays[y])
    first = '1-' + years[0]
    last = '12-' + years[len(years) - 2]
    WEs = WEs[first:last].dropna()
    WDs = WDs[first:last].dropna()
    return WDs, WEs


def Recent(WD, WE):
    recent = next(reversed(WD))
    WErecent = WE[recent]
    WDrecent = WD[recent]
    WDrecent.set_index(WDrecent.s_date, drop=True, inplace=True)
    WErecent.set_index(WErecent.s_date, drop=True, inplace=True)
    WDrecent = WDrecent[recent]['1-' + recent:'12-' + recent].dropna()
    WErecent = WErecent[recent]['1-' + recent:'12-' + recent].dropna()
    # Find nearest Friday for WD & Sunday fro WE
    i = 1
    j = 1
    while(int(WDrecent[-i:(len(WDrecent) - i + 1)].index.dayofweek) != 4):
        i += 1
    while(int(WErecent[-j:(len(WErecent) - j + 1)].index.dayofweek) != 6):
        j += 1
    # Take last 4 weeks
    firstWD = int(WDrecent[-i:(len(WDrecent) - i + 1)].index.dayofyear) - 28
    firstWE = int(WErecent[-j:(len(WErecent) - j + 1)].index.dayofyear) - 28
    rowWD = WDrecent.index.dayofyear > firstWD
    rowWE = WErecent.index.dayofyear > firstWE
    ModelWD = WDrecent.loc[rowWD, :]
    ModelWE = WErecent.loc[rowWE, :]
    return ModelWD, ModelWE


def RecentFull(dataframe):
    recent = next(reversed(dataframe))
    DF = dataframe[recent]
    DF.set_index(DF.s_date, drop=True, inplace=True)
    DF = DF[recent]['1-' + recent:'12-' + recent].dropna()
    # Find nearest Friday for WD & Sunday fro WE
    j = 1
    while(int(DF[-j:(len(DF) - j + 1)].index.dayofweek) != 6):
        j += 1
    # Take last 4 weeks
    firstW = int(DF[-j:(len(DF) - j + 1)].index.dayofyear) - 28
    row = DF.index.dayofyear > firstW
    Model = DF.loc[row, :]
    return Model


if __name__ == '__main__':
    # Update directories and files structure
    WD = {}
    WE = {}
    WDdays = {}
    WEdays = {}
    # Organize file structure if needed
    FileStructure()
    # Dowload data files to populate directory
    DownloadFiles()
    # Extract any zip files
    ExtractFiles()
    # Check to see which folders have been updated
    updatedFolders = OrganizeFiles()
    # Create DataFrame for full years
    WD, WE = CreateYearFrames(updatedFolders)
    # Create Daily Usage
    WDdays, WEdays = YearsDaily(WD, WE)
    # Functions to import extracted features and find most recent files
    # WDdays, WEdays = Import('daily')
    # Full = {}
    # Full = cd.Import('fullyear')
    # recentWD = next(reversed(WD))
