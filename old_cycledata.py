import pandas as pd
from lxml import objectify, html
import math
import os
import requests
import zipfile
import numpy as np
from PyQt4.QtGui import *
from PyQt4.QtCore import *
from PyQt4.QtWebKit import *
import sys

i_rng = pd.date_range('2015-01-01', '2015-01-01 23:45:00', freq='15min').time
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


def custom_resampler(array_like):
    return np.sum(array_like) / 14


def FormatEntries(dataframe, station_id):
    entry_index = dataframe.s_id == station_id
    dataframeE = dataframe.loc[entry_index, ['s_id', 's_date']]
    dataframeE.set_index('s_date', inplace=True)
    dataframeE = dataframeE.resample(
        "30Min", how=custom_resampler, fill_method='pad')
    return dataframeE


def FormatExits(dataframe, station_id):
    exit_index = dataframe.e_id == station_id
    dataframeEx = dataframe.loc[exit_index, ['e_date', 'e_id']]
    dataframeEx.set_index('e_date', inplace=True)
    dataframeEx = dataframeEx.resample(
        "30Min", how=custom_resampler, fill_method='pad')
    return dataframeEx


def SeperateWeek(dataframe, station_id):
    sw_time = dataframe.s_date.apply(lambda x: x.weekday() < 5)
    ew_time = dataframe.e_date.apply(lambda x: x.weekday() < 5)
    s_counts = dataframe.loc[sw_time, ['s_id', 's_date']]
    e_counts = dataframe.loc[ew_time, ['e_date', 'e_id']]
    WeekE = FormatEntries(s_counts, station_id)
    WeekEx = FormatExits(e_counts, station_id)
    return WeekE, WeekEx


def f(x):
    return x[0] - x[1]


def CalcDiff(dataframeE, dataframeEx):
    dataframe = pd.concat([dataframeE, dataframeEx], axis=1)
    dataframe.fillna(value=0, inplace=True)
    dataframe['count_diff'] = dataframe.apply(f, axis=1)
    return dataframe


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
    archive_links = tree.xpath('//@href')
    archive_links = archive_links[2:18]
    return archive_links


def DownloadFiles(directory):
    urls = GetURLs()
    new_path = directory + '\\' + 'RawData'
    os.mkdir(new_path)
    os.chdir(new_path)
    res = []
    i = 0
    for x in urls:
        res = requests.get(x)
        res.raise_for_status()
        if(x[-4:] == '.csv'):
            with open(str(urls[i][-19:]), "wb") as file:
                file.write(res.content)
        elif(x[-4:] == '.zip'):
            with open(urls[i][-28:], "wb") as file:
                file.write(res.content)
        i += 1


def ExtractFiles(directory):
    new_dir = directory + '\\' + 'RawData'
    os.chdir(new_dir)
    # Read all filenames and extract
    file_names = []
    for folderName, subfolders, filenames in os.walk(new_dir):
        print('The current folder is ' + folderName)
        for subfolder in subfolders:
            print('SUBFOLDER OF ' + folderName + ': ' + subfolder)
        for filename in filenames:
            print('FILE INSIDE ' + folderName + ': ' + filename)
            if(filename[-4:] == '.zip'):
                new_path = new_dir + '\\' + filename[-8:-4]
                os.mkdir(new_path)
                testZip = zipfile.ZipFile(filename)
                file_names.append(testZip.namelist())
                testZip.extractall(new_path)
                testZip.close()


def ReadFiles(directory):
    # Read all csv files within directory
    # Return dataframe of all csvs combined
    os.chdir(directory)
    DF = pd.DataFrame()
    for filename in os.listdir(directory):
        if(filename[-4:] == '.csv'):
            print("Reading: " + filename)
            Dfile = pd.read_csv(filename, parse_dates=[1, 3], dayfirst=True, usecols=[1, 3, 4, 6, 7],
                                na_values=0, names=['Duration', 'e_date', 'e_id', 's_date', 's_id'],
                                header=None, skiprows=1, dtype={'Duaration': np.int32, 's_id': np.int32, 'e_id': np.int32}).dropna()
            DF = DF.append(Dfile)
    return DF
