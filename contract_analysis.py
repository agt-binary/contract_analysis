#import matplotlib
#matplotlib.use('Agg')
import pandas as pd
import numpy as np
import os
import sys
import matplotlib.pyplot as plt
import matplotlib
import pickle
import re
import datetime as dt
import time
#from prep_mt5_feeds import *
matplotlib.style.use('seaborn')
from matplotlib.ticker import FormatStrFormatter
from matplotlib.offsetbox import AnchoredText

def get_info_from_shortcode(shortcode):
    # CALL_FRXUSDJPY_10_1530022140_5T_S0P_0
    # TICKLOW_R_50_1.74_1530093117_5t_1
    shortcode = shortcode.upper() 
    if shortcode.startswith('TICK'):
        tickhighlow = True
        shortcode += '_0'
    else:
        tickhighlow = False
    L = shortcode.split('_')
    start_epoch = L[-4] #int(L[-4].strip('F'))
    expiry_time = L[-3] #L[-3].strip('F')
    stake_str = L[-5]
    stake = float(stake_str)
    bet_type = L[0]
    underlying = shortcode.strip(bet_type+'_').split('_'+stake_str)[0]
    underlying = underlying.replace('FRX', 'frx')
    contract_date = pd.to_datetime(start_epoch.strip('F'), unit='s').date().strftime('%-d-%b-%y')   
    dates_of_interest = []
    start_date = pd.to_datetime(start_epoch.strip('F'), unit='s')
    rvalue = {'start': start_epoch, 'end': expiry_time, 'stake': stake, 
              'underlying': underlying, 'bet_type': bet_type,
              'date': contract_date, 'tickhighlow': tickhighlow}
    return rvalue

# tests
# shortcode = 'CALL_FRXUSDJPY_10_1530022140_5T_S0P_0'
# print(get_info_from_shortcode(shortcode))
# shortcode = 'TICKLOW_R_50_1.74_1530093117_5t_1'
# print(get_info_from_shortcode(shortcode))

def draw_charts(shortcode, before=1, after=1, buytime=None, won=False, payout=1, profit=1):
    info = get_info_from_shortcode(shortcode)
    start_epoch = int(info['start'].strip('F'))
    expiry_time = info['end'].strip('F')
    underlying = info['underlying']
    tickhighlow = info['tickhighlow']
    dates_of_interest = []
    try:
        end_epoch_0 = int(expiry_time)
    except:
        end_epoch_0 = start_epoch + 10*60
    if not buytime is None:
        buy_epoch = pd.to_datetime(buytime, format='%Y/%m/%d  %H:%M:%S').dt.total_seconds()
    else:
        buy_epoch = start_epoch
    epochs_of_interest = [buy_epoch, start_epoch, end_epoch_0]
    dates_of_interest = [pd.to_datetime(x, unit='s').date() for x in epochs_of_interest]
    dates_of_interest = sorted(list(set(dates_of_interest)))
    dates_of_interest = [x.strftime('%-d-%b-%y') for x in dates_of_interest]
    #print('number of dates of interest:', len(dates_of_interest))
    #return dates_of_interest
    #df = 
    ##
    df_list = []
    df2_list = []
    for date_of_interest in dates_of_interest:
        combined_feed_path = os.path.join('/feed/combined', underlying, date_of_interest+'.fullfeed')
        oz_feed_path = os.path.join('/feed/oz', underlying, date_of_interest+'-fullfeed.csv')
        if os.path.exists(combined_feed_path):
            _df = pd.read_csv(combined_feed_path, sep=' ', header=None,
                             error_bad_lines=False, warn_bad_lines=False)
            _df.columns = ['time', 'time_min', 'bid', 'ask', 'mid', 'LP']
            _df['date'] = pd.to_datetime(date_of_interest) #pd.to_datetime('2018-06-26')
            _df['datetime'] = pd.to_datetime(_df['date'].astype(str)+' '+_df['time'].astype(str))
            _df['epoch'] = (_df['datetime'] - dt.datetime(1970,1,1)).dt.total_seconds()
            df_list.append(_df)
        if os.path.exists(oz_feed_path):
            _df2 = pd.read_csv(oz_feed_path, header=None, names=['epochf', 'bid', 'ask', 'mid', 'mid3', 'LP', 'blank'],
                                                       error_bad_lines=False, warn_bad_lines=False)
            _df2['epoch'] = _df2['epochf'].astype(int)
            _df2['datetime'] = pd.to_datetime(_df2['epoch'], unit='s')
            _df2['date'] = _df2['datetime'].dt.date
            df2_list.append(_df2)
    if len(df_list) > 0:
        df_combined = pd.concat(df_list)
        df_combined.sort_values(by='epoch', inplace=True)
        df_combined = df_combined[pd.to_datetime(df_combined['date']) > pd.to_datetime('2000-01-01')]
    else:
        df_combined = pd.DataFrame()
    if len(df2_list) > 0:
        df_oz = pd.concat(df2_list)
        df_oz.sort_values(by='epochf', inplace=True)
        df_oz = df_oz[pd.to_datetime(df_oz['date']) > pd.to_datetime('2000-01-01')]
    else:
        df_oz = pd.DataFrame()
    if len(df_combined)*len(df_oz) == 0:
        pass
        #print(shortcode, len(df_combined), len(df_oz))
        #return None
    contract_t1 = pd.to_datetime(int(start_epoch), unit='s')
    contract_mask1 = df_combined['datetime'] >= contract_t1
    if sum(contract_mask1) <= 2:
        pass
        #print(shortcode, '\nnum_ticks after contract start:', sum(contract_mask1))
        #return None
    if 'T' in str(expiry_time):
        num_ticks = int(expiry_time.strip('T'))+1 - int(tickhighlow)
        # tickhigh / ticklow exception
        end_epoch = int(df_combined[contract_mask1].head(num_ticks+1)['epoch'].max())
        # For tick-trades, widen the context.
        before = 2.0
        after = 2.0
        if end_epoch-start_epoch>100:
            print('num ticks:', num_ticks)
            print('duration:', end_epoch-start_epoch)
            print('short code:', shortcode)
            print('profit:', round(profit,4))
            print(df_combined[contract_mask1].head(num_ticks+1))
    else:
        end_epoch = int(expiry_time)
    duration = end_epoch - start_epoch
    context_t1 = pd.to_datetime(start_epoch-before*duration, unit='s')
    context_t2 = pd.to_datetime(end_epoch+after*duration, unit='s')
    contract_t2 = pd.to_datetime(end_epoch, unit='s')
    contract_mask2 = df_combined['datetime'] <= contract_t2
    contract_mask = contract_mask1 & contract_mask2
    '''
    print(shortcode, '\n',
          'start and end epochs:', start_epoch, end_epoch, '\n',
          'duration:', duration, '\n',
          'contract and context intervals:', [(contract_t1, contract_t2), (context_t1, context_t2)])
    '''
    if len(df_combined) > 0:
        context_mask1 = df_combined['datetime']>=context_t1
        context_mask2 = df_combined['datetime']<=context_t2
        context_mask = context_mask1 & context_mask2
        context_exists = True
    else:
        context_exists = False
    if len(df_oz) > 0:
        oz_mask1 = df_oz['datetime']>=context_t1
        oz_mask2 = df_oz['datetime']<=context_t2
        oz_mask = oz_mask1 & oz_mask2
        oz_exists = True
    else:
        oz_exists = False
    ##    
    fig = plt.figure(figsize=(20,9))
    ax = plt.subplot(111)
    ax.yaxis.set_major_formatter(FormatStrFormatter('%.5f'))
    ax.xaxis.set_major_formatter(FormatStrFormatter('%.0f'))
    if context_exists:
        x_context = df_combined[context_mask]['epoch'].values #- start_epoch
        y_context = df_combined[context_mask]['mid'].values
        ax.plot(x_context, y_context, 'k.--', label='combined feed')
        #
        x_contract = df_combined[contract_mask]['epoch'].values #- start_epoch
        y_contract = df_combined[contract_mask]['mid'].values
        ax.plot(x_contract, y_contract, 'r', label='contract')
        #
    if oz_exists:
        x_oz = df_oz[oz_mask]['epochf'].values #- start_epoch
        y_oz = df_oz[oz_mask]['mid'].values
        ax.plot(x_oz, y_oz, 'b', label='oz feed')
        #
    __df = df_combined[(df_combined['epoch']>start_epoch)]
    entry = __df['epoch'].head(9).min()
    x0 = df_combined[df_combined['epoch'].astype(int) == int(entry)]['epoch'].values #- start_epoch
    #x0 = [time.strftime('%H:%M:%S',time.gmtime(x)) for x in x0]
    y0 = df_combined[df_combined['epoch'].astype(int) == int(entry)]['mid'].values
    ax.plot(x0,y0, 'y*', label='entry spot', markersize=20)
    #
    x_barrier = x_contract[x_contract>=x0]#np.asarray([x for x in list(x_oz) if ((x>=contract_t1) and (x<=contract_t2))])
    y_barrier = y0*np.ones_like(x_barrier)
    ax.plot(x_barrier, y_barrier, 'g', label='barrier')
    #plt.xticks([0,entry-start_epoch,end_epoch-start_epoch])
    plt.title(time.strftime("%a, %d/%m/%Y-%H:%M:%S",time.gmtime(start_epoch))
              +' '+underlying+' feed for examining '+shortcode)
    plt.legend(loc="best", shadow=True, fancybox=True)
    if won:
        anchored_text = AnchoredText("WON!\nPayout: "+str(round(payout,4))+"\nProfit: "+str(round(profit,4)), loc='lower right',                                        prop=dict(size="xx-large", color="red"))
    else:
        anchored_text = AnchoredText("Lost.\nPayout: "+str(round(payout,4))+"\nLoss: "+str(round(profit,4)), loc='lower right',
                                     prop=dict(size='xx-large', color="green"))
    ax.add_artist(anchored_text)
    return ax
