'''
Description
'''

try:
    from selenium import webdriver
except ImportError:
    print('\n####################################################################')
    print('SELENIUM NOT AVAILABLE!!! You can only run tests using HAR capturer!!!')
    print('####################################################################\n')
# import sys, os, time, pickle, socket, json, subprocess, traceback, multiprocessing, subprocess
import time 
# import stats                  # Module not found
# import sideTrafficGenerator   # Module not found
from pythonLib import *         # Custom python file
from functools import wraps
import errno
import os
import signal

class TimeoutError(Exception):
    pass

def timeout(seconds=10, error_message=os.strerror(errno.ETIME)):
    def decorator(func):
        def _handle_timeout(signum, frame):
            raise TimeoutError(error_message)

        def wrapper(*args, **kwargs):
            signal.signal(signal.SIGALRM, _handle_timeout)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
            return result

        return wraps(func)(wrapper)

    return decorator

class Driver(object):
    def __init__(self, chromeDriverPath, browserPath, options, pageLoadTimeOut=None):
        self.chromeDriverPath = chromeDriverPath
        self.browserPath      = browserPath
        self.options          = options
        self.pageLoadTimeOut  = pageLoadTimeOut
        self.driver           = None    

    @timeout(20)
    def open(self):
        webdriver.ChromeOptions.binary_location = self.browserPath
        chromeService = webdriver.chrome.service.Service(self.chromeDriverPath)
        
        self.driver = webdriver.Chrome(service=chromeService, options=self.options)
        
        if self.pageLoadTimeOut:
            self.driver.set_page_load_timeout(self.pageLoadTimeOut)

    @timeout(20)
    def close(self):
        self.driver.close()
        self.driver.quit()
        
    def get(self, url):
        self.driver.get(url)

    def clearCacheAndConnections(self):
        self.driver.execute_script("return chrome.benchmarking.clearCache();")
        self.driver.execute_script("return chrome.benchmarking.clearHostResolverCache();")
        self.driver.execute_script("return chrome.benchmarking.clearPredictorCache();")
        self.driver.execute_script("return chrome.benchmarking.closeConnections();")


def initialize():
    configs = Configs()
    
    configs.set('waitBetweenLoads'  , 1)
    configs.set('waitBetweenRounds' , 1)
    configs.set('rounds'            , 10)
    configs.set('pageLoadTimeout'   , 120)
    configs.set('tcpdump'           , True)
    configs.set('serverIsLocal'     , False)
    configs.set('runQUICserver'     , True)
    configs.set('runTcpProbe'       , False)
    configs.set('doSideTraffic'     , False)
    configs.set('closeDrivers'      , False)
    configs.set('clearCacheConns'   , True)
    configs.set('separateTCPDUMPs'  , False)
    configs.set('doStats'           , False)
    configs.set('browserPath'       , False)
    configs.set('doSecondDL'        , False)    #On a phone, we need to close browser for back-to-back runs which prevents 0-RTT for QUIC. If this is True, for QUIC downloads, it does 2, and save the result (HAR) for the second one which has 0-RTT
    configs.set('backgroundPings'   , False)
    configs.set('quicServerIP'      , None)
    configs.set('httpServerIP'      , None)
    configs.set('httpsServerIP'     , None)
    configs.set('modifyEtcHosts'    , True)
    configs.set('quicProxyIP'       , '[URL of server running QUIC proxy]')
    configs.set('httpsProxyIP'      , '[URL of server running HTTP proxy]')
    configs.set('cases'             , 'http,https,quic')
    configs.set('quicProxyPort'     , '443')
    configs.set('httpsProxyPort'    , '443')
    configs.set('platform'          , 'linux64')
    configs.set('against'           , 'GCP')        #Possible inputs are: GCP (Google Cloud Platform), GAE (Google App Engine), or EC2 (Amazon)
    configs.set('quic_server_path'  , '')
    configs.set('mainDir'           , os.path.abspath('../data') + '/results')
    configs.set('extPath'           , os.path.abspath('extension_cache_remover'))
    
    configs.read_args(sys.argv)
    
    '''
    Important: the following MUST be done AFTER read_args in case "--against" gets overridden 
    '''
    if configs.get('against') == '[your server name]':
        configs.set('host', {'quic'         :'[URL of host running QUIC server]',
                             'http'         :'[URL of host running HTTP server]',
                             'https'        :'[URL of host running HTTPS server]',
                             'https-proxy'  :'[URL of host running HTTP proxy server]',
                             'quic-proxy'   :'[URL of host running QUIC proxy server]',})
        
        
    configs.check_for(['testDir', 'testPage', 'networkInt'])
    
    if configs.get('testDir').endswith('/'):
        configs.set( 'testDir', configs.get('testDir')[:-1] )
    
    # configs.set('chromedriver', selectChromeDriverPath(configs.get('browserPath'), configs.get('platform')))
    
    configs.set('testDir', configs.get('mainDir') + '/' + configs.get('testDir') )
    
    if os.path.isdir(configs.get('testDir')):
        print('Test directory already exists! Use another name!')
        sys.exit()
    
    #Creating the necessary directory hierarchy
    PRINT_ACTION('Creating the necessary directory hierarchy', 0)        
    testDir         = configs.get('testDir')
    resultsDir      = '{}/resultsDir'.format(testDir)
    statsDir        = '{}/statsDir'.format(testDir)
    userDirs        = '{}/userDirs'.format(testDir)
    screenshotsDir  = '{}/screenshots'.format(testDir)
    dataPaths       = '{}/dataPaths'.format(testDir)
    netLogs         = '{}/netLogs'.format(testDir)
    tcpdumpDir      = '{}/tcpdumps'.format(testDir)
    tcpdumpFile     = '{}/{}_tcpdump.pcap'.format(testDir, os.path.basename(testDir))
    configsFile     = '{}/{}_configs.txt'.format(testDir, os.path.basename(testDir))
      
    os.system('mkdir -p {}'.format(resultsDir))
    os.system('mkdir -p {}'.format(statsDir))
    os.system('mkdir -p {}'.format(userDirs))
    os.system('mkdir -p {}'.format(screenshotsDir))
    os.system('mkdir -p {}'.format(dataPaths))
    os.system('mkdir -p {}'.format(netLogs))
    os.system('mkdir -p {}'.format(tcpdumpDir))
     
    #Write configs to file (just for later reference)
    configs.write2file(configsFile)
    
    cases         = configs.get('cases').split(',')
    methods       = {'quic'         :'https', 
                     'http'         :'http', 
                     'https'        :'https',
                     'https-proxy'  :'https', 
                     'quic-proxy'   :'https'}
    
    
    uniqeOptions  = {'quic' : [
                             '--enable-quic',
                             '--origin-to-force-quic-on={}:443'.format(configs.get('host')['quic']),
                             '--quic-host-whitelist={}'.format(configs.get('host')['quic']),
                             ],
                    
                    'quic-proxy' : [
                             '--enable-quic',
                             '--origin-to-force-quic-on={}:443'.format(configs.get('host')['quic']),
                             '--quic-host-whitelist={}'.format(configs.get('host')['quic']),
                             '--host-resolver-rules=MAP {}:443 {}:{}'.format(configs.get('host')['quic'], configs.get('quicProxyIP'), configs.get('quicProxyPort')),
                             ],
                     
                    #Because I have to use "echo" and "adb shell" to write to a file when setting flags for Chrome on Android,
                    #I need quotations and escapes and stuff. SO the "host-resolver-rule" option's quoatation for mobile is different
                    #In engineAndroid_harCapturer.py, we do uniqeOptions['quic-proxy'] = uniqeOptions['quic-proxy-mobile'] 
                    'quic-proxy-mobile' : [
                             '--enable-quic',
                             '--origin-to-force-quic-on={}:443'.format(configs.get('host')['quic']),
                             '--quic-host-whitelist={}'.format(configs.get('host')['quic']),
                             "--host-resolver-rules=\"MAP {}:443 {}:{}\"".format(configs.get('host')['quic'], configs.get('quicProxyIP'), configs.get('quicProxyPort')),
                             ],
                     
                    'http' : [
                             '--disable-quic',
                             ],
                    
                    'https': [
                             '--disable-quic',
                             ],
                    'https-proxy': [
                             '--disable-quic',
                             '--host-resolver-rules=MAP {}:443 {}:{}'.format(configs.get('host')['https'], configs.get('httpsProxyIP'), configs.get('httpsProxyPort')),
                             ],               
                    }
    
    try:
        configs.get('quic-version')
        uniqeOptions['quic'].append( '--quic-version=QUIC_VERSION_{}'.format(configs.get('quic-version')) )
        uniqeOptions['quic-proxy'].append( '--quic-version=QUIC_VERSION_{}'.format(configs.get('quic-version')) )
        uniqeOptions['quic-proxy-mobile'].append( '--quic-version=QUIC_VERSION_{}'.format(configs.get('quic-version')) )
    except KeyError:
        pass
    
    
    dIPs = {'quic'          : configs.get('quicServerIP'),
            'http'          : configs.get('httpServerIP'),
            'https'         : configs.get('httpsServerIP'),
            'https-proxy'   : configs.get('httpsProxyIP'),
            'quic-proxy'    : configs.get('quicProxyIP')
            }
    
    # modifyEtcHosts = ModifyEtcHosts()
    # if configs.get('modifyEtcHosts'):
    #     for case in cases:
    #         try:
    #             modifyEtcHosts.add([configs.get('host')[case]])
    #         except:
    #             print('\t\tmodifyEtcHosts did not add host for:', case)
    #             pass
    #         if case == 'quic-proxy':
    #             modifyEtcHosts.add([configs.get('quicProxyIP')])
    #         if case == 'https-proxy':
    #             modifyEtcHosts.add([configs.get('httpsProxyIP')])
    
    return configs, cases, methods, testDir, resultsDir, statsDir, userDirs, screenshotsDir, dataPaths, netLogs, tcpdumpDir, tcpdumpFile, uniqeOptions, modifyEtcHosts


def main():
    #The following line is to make sure the script has sudo privilage to run tcpdump
    os.system('sudo echo')


    #Setting up configs
    PRINT_ACTION('Reading configs file and args', 0)
    # configs, cases, methods, testDir, resultsDir, statsDir, userDirs, screenshotsDir, dataPaths, netLogs, tcpdumpDir, tcpdumpFile, uniqeOptions, modifyEtcHosts = initialize()
    # configs.show_all()
    
    uniqeOptions  = {'quic' : [
                            '--enable-quic',
                            '--origin-to-force-quic-on={}:443'.format("www.example.org"),
                            # '--quic-host-whitelist={}'.format(configs.get('host')['quic']),
                            '--no-proxy-server',
                            '--host-resolver-rules=MAP {}:443 {}:{}'.format("www.example.org", "10.10.1.1", "6121"),
                            ],       
                    'http' : [
                             '--disable-quic',
                             ],
                    
                    'https': [
                             '--disable-quic',
                             ],        
                }

    #Creating options
    # '''
    # IMPORTANT: --enable-benchmarking --enable-net-benchmarking: to enable the Javascript interface that allows chrome-har-capturer to flush the DNS cache and the socket pool before loading each URL.
    #            in other words, clear cache and close connections between runs! 
    # '''
    PRINT_ACTION('Creating options', 0)
    drivers         = {}
    # stat           = stats.Stats() 
    chromeOptions   = {}
    commonOptions   = ['--no-first-run']

    clearCacheConns = True
    if clearCacheConns:
        commonOptions += ['--enable-benchmarking', '--enable-net-benchmarking']

    #Creating driver instances and modifying /etc/hosts
    PRINT_ACTION('Creating driver options and modifying /etc/hosts', 0)
    cases = ['quic'] # add quic

    for case in cases:

        
        # create chrome driver options
        chromeOptions[case] = webdriver.ChromeOptions()
        
        unCommonOptions     = ['--user-data-dir={}/{}'.format('tmp', 'chrome-profile'),
                            # '--data-path={}/{}'.format(dataPaths, case),
#                                '--log-net-log={}/{}.json'.format(netLogs, case),
                            ]
        extraOptions = ['--headless', '--ignore-certificate-errors-spki-list', '--allow_unknown_root_cert']

        for option in uniqeOptions[case] + commonOptions + unCommonOptions + extraOptions :
            chromeOptions[case].add_argument(option)

        print("Chrome Options")
        print(chromeOptions[case])
        # creating driver instances
        drivers[case] = Driver("/proj/FEC-HTTP/long-quic/chromedriver_linux64/chromedriver", "/proj/FEC-HTTP/long-quic/chromium/src/out/Default/chrome", chromeOptions[case])

        drivers[case].open()


    #Firing off the tests
    PRINT_ACTION('Firing off the tests', 0)
    no_of_round = 1
    for round in range(1, no_of_round+1):
        url = "https://www.example.org"
        # stat.start()

        try:
            drivers[case].get(url)
        except Exception as e:
            print('###### EXCEPTION during {}#######'.format(testID))
            print(e)
            traceback.print_exc()
            continue
        # Stop TCP dump
        print("Title")
        print(drivers[case].driver.title)
        print("Source")
        print(drivers[case].driver.page_source)
        windowPerformance = drivers[case].driver.execute_script("return window.performance.getEntriesByType('resource');")

        # print(windowPerformance[0]['duration'])
        print(windowPerformance)

        # json dump performance resource timing

        # statsRes = stat.stop()
        # stat.save("stat.json")

        drivers[case].driver.save_screenshot('{}_{}.png'.format("screenshotsDir", "testID"))

        # Not working due to chrom not found error in execute script
        # Not sure if har-capturer solves this
        # Temp Fix , close chrome between every runs
        # if True:
            # drivers[case].clearCacheAndConnections()

        if True:
            try:
                drivers[case].close()
            except TimeoutError:
                print('Got stuck closing driver! :-s')

        waitBetweenRounds = 1
        time.sleep(waitBetweenRounds)


if __name__=="__main__":
    main()