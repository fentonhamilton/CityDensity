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
import rpy2.robjects as robjects
from rpy2.robjects.packages import importr
from rpy2.robjects import pandas2ri
import rpy2.robjects.packages as rpackages
import gc

i_rng = pd.date_range('2015-01-01', '2015-01-01 23:45:00', freq='15min').time
wd = str(os.getcwd())
years = ['2012', '2013', '2014', '2015', '2016']
filenames = ['FullYear.csv', 'Weekdays.csv', 'WeekEnds.csv', 'WeekDaily.csv', 'WeekEndDaily.csv']
station_range = range(1, 805)


class Render(QWebPage):
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
        self.valid = False
        self.oldest = dataframe.s_date.min()
        self.recent = dataframe.s_date.max()
        self.DF = self.FilterStation(dataframe)
        self.WD = pd.DataFrame()
        self.WE = pd.DataFrame()
        self.Full = pd.DataFrame()

    def FilterStation(self, dataframe):
        row_index = (dataframe.s_id == self.ID) | (dataframe.e_id == self.ID)
        StationFrame = dataframe.loc[row_index, ['e_date', 'e_id', 's_date', 's_id']]
        if len(StationFrame) > 0:
            self.valid = True
        return StationFrame

    def Format(self, type):
        if(type == 'entry'):
            row = self.DF.s_id == self.ID
            index = 's_date'
            columns = ['s_date', 's_id']
        elif(type == 'exit'):
            row = self.DF.e_id == self.ID
            index = 'e_date'
            columns = ['e_date', 'e_id']
        dataframe = self.DF.loc[row, columns]
        dataframe.set_index(index, inplace=True)
        # Add entry so that start point is beginning of day
        dt1 = pd.DatetimeIndex([self.oldest])
        dt2 = pd.DatetimeIndex([self.recent])
        dt1 = dt1.append(dt2)
        df = pd.DataFrame(data=[0, 0], index=dt1, columns=[columns[1]])
        dataframe = dataframe.append(df)
        dataframe = dataframe.resample("30Min").apply(self.custom_resampler)
        del dataframe.index.name
        return dataframe

    def custom_resampler(self, array_like):
        return np.sum(array_like) / self.ID

    def f(self, x):
        return x[0] - x[1]

    def CalcDiff(self, dataframeE, dataframeEx):
        dataframe = pd.concat([dataframeE, dataframeEx], axis=1)
        dataframe.fillna(value=0, inplace=True)
        dataframe['count_diff'] = dataframe.apply(self.f, axis=1)
        return dataframe

    def PreProcess(self, separate=False):
        # Filter to specific station
        fullE = self.Format('entry')
        fullEx = self.Format('exit')
        if(separate is True):
            # separate week
            WDentry, WEentry = SeparateWeek(fullE, index=True)
            WDexit, WEexit = SeparateWeek(fullEx, index=True)
            # Calculate entry/exit differences
            if len(WDentry) | len(WDexit) > 0:
                WDdiff = self.CalcDiff(WDentry, WDexit)
                self.WD = WDdiff.drop(['s_id', 'e_id'], axis=1)
                self.WD.count_diff = self.WD.count_diff.astype(int)
            if len(WEentry) | len(WEexit) > 0:
                WEdiff = self.CalcDiff(WEentry, WEexit)
                self.WE = WEdiff.drop(['s_id', 'e_id'], axis=1)
                self.WE.count_diff = self.WE.count_diff.astype(int)
        elif(separate is False):
            self.Full = self.CalcDiff(fullE, fullEx)
            self.Full = self.Full.drop(['s_id', 'e_id'], axis=1)
            self.Full.count_diff = self.Full.count_diff.astype(int)


def GetAddressBook():
    url = 'https://api.tfl.gov.uk/bikepoint'
    resp = requests.get(url)
    Jfile = resp.json()
    ab = []
    for i in Jfile:
        ab.append({'long': i["lon"], 'lat': i["lat"], 'id': i["id"][11:], 'name': i["commonName"]})
    addressbook = pd.DataFrame(ab)
    addressbook.id = addressbook.id.astype(int)
    addressbook.sort_values(by='id', axis=0, ascending=True, inplace=True)
    addressbook.set_index(addressbook.id, inplace=True, drop=True)
    # Find stations not listed in addressbook
    add = pd.DataFrame(index=pd.Series(range(1, max(addressbook.id) + 1)))
    DF = add.join(addressbook)
    missingStations = DF[DF.isnull().any(axis=1)].index
    addressbook.to_csv(path_or_buf='Bike_Stations.csv', columns=['long', 'lat', 'id', 'name'], index=False)
    pd.DataFrame(missingStations).to_csv(wd + '\\' + 'missing_stations.csv', index=False, header=False)
    return addressbook, missingStations


def GetDistances(addressbook):
    # Compute distance between stations
    if(len(addressbook) > 0):
        distances = pd.DataFrame(
            index=pd.Series(station_range), columns=pd.Series(station_range))
        for i in station_range:
            srow_index = addressbook['id'] == i
            start = addressbook.loc[srow_index, ['id', 'lat', 'long']]
            if(len(start) > 0):
                for j in station_range:
                    if i != j:
                        erow_index = addressbook['id'] == j
                        end = addressbook.loc[erow_index, ['id', 'lat', 'long']]
                        if(len(end) > 0):
                            delta_lat = (end.iloc[0, 1] - start.iloc[0, 1]) * math.pi / 180
                            delta_long = (end.iloc[0, 2] - start.iloc[0, 2]) * math.pi / 180
                            a = math.sin(delta_lat / 2)**2 + math.cos(start.lat * math.pi / 180) * math.cos(
                                end.lat * math.pi / 180) * math.sin(delta_long / 2)**2
                            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
                            distances[j][i] = 6371000 * c
    distances.to_csv(wd + '\\' 'Bike_Station_Distances.csv')
    return distances


def SeparateWeek(dataframe, index=False):
    if(index is True):
        w_indexer = dataframe.index.weekday < 5
        we_indexer = dataframe.index.weekday > 4
    else:
        w_indexer = dataframe.s_date.apply(lambda x: x.weekday() < 5)
        we_indexer = dataframe.s_date.apply(lambda x: x.weekday() > 4)
    Week = dataframe.loc[w_indexer, :]
    WeekEnd = dataframe.loc[we_indexer, :]
    if(index is False):
        Week.reset_index(inplace=True, drop=True)
        WeekEnd.reset_index(inplace=True, drop=True)
    # print('Weekdays and Weekends separated')
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
                                    header=None, skiprows=1,
                                    dtype={'Duaration': np.float32, 's_id': np.float32, 'e_id': np.float32}).dropna()
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


def AdjustOverlap(FullYear):
    FY = FullYear
    DFweek = {}
    DFweekEnd = {}
    for year in years:
        FY[year].set_index(FY[year].s_date, drop=True, inplace=True)
    for x in range(1, len(years)):
        current = years[x]
        previous = years[x - 1]
        FY[previous] = FY[previous].append(FY[current][previous])
    for year in years:
        path = wd + '\Features\\' + year + '\\' + year
        FY[year] = FY[year]['1-' + year:'12-' + year]
        FY[year].reset_index(inplace=True, drop=True)
        DFweek[year], DFweekEnd[year] = SeparateWeek(FY[year])
        print('Writing: ' + year + filenames[0])
        FY[year].to_csv(path + filenames[0])
        print('Writing: ' + year + filenames[1])
        DFweek[year].to_csv(path + filenames[1])
        print('Writing: ' + year + filenames[2])
        DFweekEnd[year].to_csv(path + filenames[2])
        print(year + ' YearFrame updated')
    return FY, DFweek, DFweekEnd


def CreateYearFrames(updatedFolder):
    DF = {}
    DFweek = {}
    DFweekEnd = {}
    for year in years:
        pt_path = wd + '\Features\\' + year
        full_path = pt_path + '\\' + year
        i = 0
        for x in range(0, 3):
            if(os.path.isfile(full_path + filenames[x])):
                i += 1
        if((i == 3) and (updatedFolder[year] is False)):
            print('Features already extracted for year: ' + year)
            continue
        DF[year] = ReadFiles(wd + '\\' + 'RawData' + '\\' + year)
        if not os.path.exists(pt_path):
            os.mkdir(pt_path)
        DF[year]
        DFweek[year], DFweekEnd[year] = SeparateWeek(DF[year])
        print('Writing: ' + year + filenames[0])
        DF[year].to_csv(full_path + filenames[0])
        print('Writing: ' + year + filenames[1])
        DFweek[year].to_csv(full_path + filenames[1])
        print('Writing: ' + year + filenames[2])
        DFweekEnd[year].to_csv(full_path + filenames[2])
        print(year + ' YearFrame completed')
    return DF, DFweek, DFweekEnd


def YearsDaily(Weekdays, WeekEnds):
    WeekDaily = {}
    WeekEndDaily = {}
    for year in years:
        path = wd + "\Features\\" + year
        full_path = path + '\\' + year
        i = 0
        for x in range(3, 5):
            if(os.path.isfile(full_path + filenames[x])):
                i += 1
        if((i == 2) and (updatedFolder[year] is False)):
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
        print('Writing: ' + filenames[3])
        WeekDaily[year].to_csv(full_path + filenames[3])
        print('Writing: ' + filenames[4])
        WeekEndDaily[year].to_csv(full_path + filenames[4])
    return WeekDaily, WeekEndDaily


def FileStructure():
    try:
        os.mkdir(wd + "\Features")
        os.mkdir(wd + "\RawData")
    except:
        print('Directories already exist!')


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
                print('Reading: ' + year + 'WeekDaily.csv')
                WDdaily[year] = pd.read_csv(path + '\\' + year + 'WeekDaily.csv', parse_dates=0, index_col=0,
                                            dtype={'Count': np.float32})
                print('Reading: ' + year + 'WeekEndDaily.csv')
                WEdaily[year] = pd.read_csv(path + '\\' + year + 'WeekEndDaily.csv', parse_dates=0, index_col=0,
                                            dtype={'Count': np.float32})
            elif(type == 'fullyear'):
                print('Reading: ' + year + 'FullYear.csv')
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
    last = '12-' + years[-1]
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
    lastWD = int(WDrecent[-i:(len(WDrecent) - i + 1)].index.dayofyear)
    lastWE = int(WErecent[-j:(len(WErecent) - j + 1)].index.dayofyear)
    firstWD = lastWD - 28
    firstWE = lastWE - 28
    rowWD = (WDrecent.index.dayofyear > firstWD) & (
        WDrecent.index.dayofyear < (lastWD + 1))
    rowWE = (WErecent.index.dayofyear > firstWE) & (
        WErecent.index.dayofyear < (lastWE + 1))
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
    # Take last 2 weeks
    lastW = int(DF[-j:(len(DF) - j + 1)].index.dayofyear)
    firstW = lastW - 14
    row = (DF.index.dayofyear > firstW) & (DF.index.dayofyear < (lastW + 1))
    Model = DF.loc[row, :]
    return Model


def CalcSpeeds(dataframe):
    # WARNING: long running time
    dataframe.reset_index(drop=True, inplace=True)
    dataframe.Duration = dataframe.Duration.astype(float)
    dataframe.e_id = dataframe.e_id.astype(int)
    dataframe.s_id = dataframe.s_id.astype(int)
    speed = pd.Series()
    try:
        distances = pd.read_csv(
            wd + '\\' "Bike_Station_Distances.csv", index_col=0)
    except:
        print('No distances file. Must create this file first!')
        return
    for x in dataframe.index:
        row_index = dataframe.iloc[x]['s_id'] - 1
        column_index = dataframe.iloc[x]['e_id'] - 1
        distance = distances.iloc[row_index][column_index]
        av_speed = distance / dataframe.iloc[x]['Duration']
        speed = speed.append(pd.Series([av_speed]))
    speed.reset_index(drop=True, inplace=True)
    dataframe['speed'] = speed
    return dataframe


def Transform(dataframe, start, end):
    # start and end integer numbers of 15min intervals 08:00 = 32
    counts = pd.Series()
    hours = pd.Series(
        pd.date_range(start='2015-01-01', periods=96, freq='15Min')).dt.time
    adjacency = pd.DataFrame(
        index=pd.Series(station_range), columns=pd.Series(station_range))
    dataframe.Duration = dataframe.Duration.astype(int)
    dataframe.s_id = dataframe.s_id.astype(int)
    dataframe.e_id = dataframe.e_id.astype(int)
    dataframe.set_index(dataframe.s_date, inplace=True)
    dataframe.set_index(dataframe.index.time, inplace=True)
    peak_time = (dataframe.index > hours[start]) & (
        dataframe.index < hours[end])
    DF = dataframe.loc[
        peak_time, ['s_id', 'e_id', 's_date', 'e_date', 'Duration']]
    DF.e_id = DF.e_id.astype(int)
    DF.s_id = DF.s_id.astype(int)
    for x in range(0, len(DF)):
        sid = DF.iloc[x][0]
        eid = DF.iloc[x][1]
        row_indexer = (DF.s_id == sid) & (DF.e_id == eid)
        multiples = DF.loc[row_indexer, ['s_id', 'e_id']]
        counts = counts.append(pd.Series([len(multiples)]))
        adjacency[eid][sid] = len(multiples)
    counts.reset_index(drop=True, inplace=True)
    DF.reset_index(drop=True, inplace=True)
    DF['counts'] = counts
    adjacency.fillna(0, inplace=True)
    # adjacency[end][start]
    return adjacency, DF


def RunWDModel(recent):
    pandas2ri.activate()
    # R package names
    packnames = ('forecast')
    if all(rpackages.isinstalled(x) for x in packnames):
        have_tutorial_packages = True
    else:
        have_tutorial_packages = False
    if not have_tutorial_packages:
        # import R's utility package
        utils = rpackages.importr('utils')
        # select a mirror for R packages
        utils.chooseCRANmirror(ind=1)  # select the first mirror in the list
    if not have_tutorial_packages:
        # R vector of strings
        from rpy2.robjects.vectors import StrVector
        # file
        packnames_to_install = [x for x in packnames if not rpackages.isinstalled(x)]
        if len(packnames_to_install) > 0:
            utils.install_packages(StrVector(packnames_to_install))
    # Import R packages
    forecast = importr('forecast')
    base = importr('base')
    # Model subset of data for particular station
    jump = 3  # skip weekend
    output = pd.DataFrame(columns=['count_diff', 'DateTime', 'Type', 'ID'])
    absent = []
    errors = []
    for x in station_range:
        SepModel = Model(recent, x)
        if SepModel.valid is False:
            absent.append(x)
            continue
        SepModel.PreProcess(separate=True)
        SepModel.WD = SepModel.WD[:480]
        if(len(SepModel.WD) > 0):
            if(x == 1):  # Only needs to be run once, same for all stations
                WD_dates = SepModel.WD.index
                new = pd.to_datetime((np.asarray(WD_dates[-1].year, dtype='datetime64[Y]')-1970)+(np.asarray((WD_dates[-1].dayofyear+jump), dtype='timedelta64[D]')-1))
                new_dates = pd.DatetimeIndex(start=new, freq='30Min', periods=48*4)
            SepModel.WD.reset_index(inplace=True, drop=True)
            gc.collect()
            robjects.r('order = c(2,0,3)')
            robjects.r('sorder = c(1,1,2)')
            robjects.r('seasonal = list(order=sorder, period=48)')
            DF = pandas2ri.py2ri(SepModel.WD)
            robjects.r.assign('df', DF)
            try:
                robjects.r('fit = Arima(df, order=order, seasonal=seasonal, method="CSS")')
            except:
                errors.append(x)
                continue
            f_cast = robjects.r('f_cast = forecast(fit, h=4*48)')
            arima_mean = np.array(f_cast.rx('mean'))
            robjects.r('rm(list = ls(all = TRUE))')
            robjects.r('gc()')
            results = pd.DataFrame({'count_diff': arima_mean.flatten()}).round()
            results.count_diff = results.count_diff.astype(int)
            results['DateTime'] = new_dates
            results['Type'] = 'Forecast'
            results['ID'] = x
            SepModel.WD['DateTime'] = WD_dates
            SepModel.WD['Type'] = 'Historic'
            SepModel.WD['ID'] = x
            out = SepModel.WD.append(results)
            output = output.append(out)
            del f_cast
            del DF
            del SepModel
            gc.collect()
    output.ID = output.ID.astype(int)
    output.count_diff = output.count_diff.astype(int)
    output.reset_index(inplace=True, drop=True)
    path = wd + '\Model'
    if not os.path.exists(path):
                os.mkdir(path)
    output.to_csv(path + '\\' 'ModelOutput.csv')
    return output, absent, errors

if __name__ == '__main__':
    # Update directories and files structure
    FY = {}
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
    FY, WD, WE = CreateYearFrames(updatedFolders)
    # Adjust any overlaps within the year frames
    FY, WD, WE = AdjustOverlap(FY)
    # Create Daily Usage
    WDdays, WEdays = YearsDaily(WD, WE)
    # Find most recent 2 weeks
    recent = cd.RecentFull(FullYear)
    # Run R Model (WARNING: long runtime)
    output = RunWDModel(recent)
