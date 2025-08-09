# utils/data_fetching.py
from django.db import connections
from django.db.models import Q
from django.conf import settings
from datetime import datetime
import pandas as pd
from signali_strojev.models import TimConfig, TimDefinition, StrojEntry
from sqlalchemy import create_engine, text
import os

server_domain = 'postgres'

operacija_map_global = {
    'Litje': '10',
    'Peskanje': '30',
    'Obdelava': '40',
    'HPWD + Pranje': '50',
    'Pranje': '50',
    'Pranje 1': '50',
    'HPWD + Pranje 2': '50',
    'Preizkus tesnosti': '60',
    'Montaža': '60',
    'Montaža 1': '60',
    'Montaža 2 + PT': '70',
    'Montaža + PT1': '60',
    'Montaža + PT2': '70',
    'Pregledovanje': '70',
    'Vizualna kontrola LTH': '70',
    'Firewall': '70',
    'Embaliranje': '80',
}

operacija_map_system_housing = {
    'Litje': '10',
    'Peskanje': '30',
    'Obdelava': '40',
    'Impregnacija': '50',
    'Pranje': '60',
    'Preizkus tesnosti': '70',
    'Embaliranje': '80',
    'Firewall': '200',
}

opravilo_map_global = {
            'Litje':'2020',
            'Peskanje':'2100',
            'Žarjenje':'2121',
            'Obdelava': '2230',
            'Pranje': '2240',
            'Pranje 1': '2240',
            'HPWD + Pranje 2': '2240',
            'Preizkus tesnosti': '2250',
            'Montaža': '2250',
            'Montaža + PT1': '2250',
            'Montaža + PT2': '2250',
            'Pregledovanje': '2150',
            'Postaja': '2230',
        }


meseci_dict = {1: 'Januar', 2: 'Februar', 3: 'Marec', 4: 'April', 5: 'Maj', 6: 'Junij', 7: 'Julij',
               8: 'Avgust', 9: 'September', 10: 'Oktober', 11: 'November', 12: 'December'}
meseci_dict_inv = dict((v,k) for k,v in meseci_dict.items())
meseci_dict_inv_kratice = dict((v[:3],k) for k,v in meseci_dict.items())
dnevi_dict = {0: 'Po', 1: 'To', 2: 'Sr', 3: 'Če', 4: 'Pe', 5: 'So', 6: 'Ne'}
dnevi_dict_full = {0: 'Ponedeljek', 1: 'Torek', 2: 'Sreda', 3: 'Četrtek', 4: 'Petek', 5: 'Sobota', 6: 'Nedelja'}

def fetch_production_data_per_stroj_izmena(list_of_stroji, start_date, end_date):
    """
    Fetches production data per machine (stroj) and shift (izmena) between start_date and end_date.

    Parameters:
    - list_of_stroji: List of machines (stroji) to include.
    - start_date: Start date (datetime.date object)
    - end_date: End date (datetime.date object)

    Returns:
    - data_df: Pandas DataFrame with columns 'Stroj', 'Izmena', 'Dobri', 'Izmet'
    """
    # Construct the SQL query
    query = '''
    SELECT "Stroj", "Izmena", SUM("Kolicina celice") AS "Dobri", SUM("Izmet celice") AS "Izmet"
    FROM realizacija_proizvodnje_postaje_opravila
    WHERE "Dnevni datum" BETWEEN %(start_date)s AND %(end_date)s
    AND "Stroj" IN %(list_of_stroji)s
    GROUP BY "Stroj", "Izmena"
    '''
    params = {
        'start_date': start_date,
        'end_date': end_date,
        'list_of_stroji': tuple(list_of_stroji),
    }
    # Connect to external_db and execute query
    with connections['external_db'].cursor() as cursor:
        cursor.execute(query, params)
        columns = [col[0] for col in cursor.description]
        data = cursor.fetchall()
    # Convert to DataFrame
    data_df = pd.DataFrame(data, columns=columns)
    return data_df


def create_engine_postgres_pool(DATABASE_URL, echo=False):
    # Customize the connection pool
    engine = create_engine(
        DATABASE_URL,
        echo=echo,
        poolclass=QueuePool,  # Use a QueuePool, which is default but can be explicitly stated for clarity
        pool_size=10,         # The number of connections to keep open inside the pool
        max_overflow=20,      # The number of connections to allow in overflow, beyond the pool_size
        pool_timeout=30,      # Number of seconds to wait before giving up on getting a connection from the pool
        pool_recycle=1800,    # Recycle connections after 30 minutes
    )
    return engine

def dedup_columns_space(columns):
    seen = set()
    deduped = []
    for col in columns:
        new_col = col
        counter = 1
        while new_col in seen:
            counter += 1
            spaces = counter * ' '
            new_col = f"{spaces}{col}"
        deduped.append(new_col)
        seen.add(new_col)
    return deduped

def pivot_and_merge_with_plan(data_df, date_column_aux, radios_dtm):
    plan_sum = data_df.groupby(['Stroj', 'Artikel'])['Plan'].first().reset_index()
    plan_sum.set_index(['Stroj', 'Artikel'], inplace=True)
    data_df_pivot = data_df.pivot_table(
        index=['Stroj', 'Artikel'],
        columns=date_column_aux,
        values=['Kolicina celice', 'Izmet celice'],
        aggfunc='sum',
        fill_value=0
    )
    
    data_df_pivot[('Plan', '')] = plan_sum['Plan']
    data_df_pivot.reset_index(inplace=True)
    strojartikelplan_cols = list(data_df_pivot.columns[:2]) + [data_df_pivot.columns[-1]]
    data_df_pivot.set_index(strojartikelplan_cols, inplace=True)
    new_columns = []
    for col in data_df_pivot.columns:
        if col == 'Plan':
            new_columns.append(('Plan', ''))
        else:
            new_columns.append(col)
    data_df_pivot.columns = pd.MultiIndex.from_tuples(new_columns)
    data_df_pivot = reorder_columns_by_time_period(data_df_pivot, radios_dtm)
    
    return data_df_pivot

def filter_stroj_postaja(df, vrsta_strojev, tagname_tim):
    if vrsta_strojev == 'Preizkus tesnosti' and tagname_tim == 'mopf':
        # df['Postaja'] = pd.to_numeric(df['Postaja'], errors='coerce')
        # breakpoint()
        df = df.reset_index(drop=True)
        condition_tg601 = df['Stroj'] == 'TG601'
        condition_postaja_50 = df['Postaja'] == '50'
        mask = ~condition_tg601 | (condition_tg601 & condition_postaja_50)
        df = df[mask]
        df = df.reset_index(drop=True)
        
        condition_tg401 = df['Stroj'] == 'TG401'
        condition_postaja_60 = df['Postaja'] == '60'
        mask = ~condition_tg401 | (condition_tg401 & condition_postaja_60)
        df = df[mask]
        
        return df

    
    elif vrsta_strojev == 'Preizkus tesnosti' and tagname_tim == 'stgh_i_ii__hag':
        return df
        
    elif vrsta_strojev == 'Obdelava' and tagname_tim == 'stellantis':
        return df
    
    return df

def adjust_for_preizkus_tesnosti(df, vrsta_strojev, tagname_tim):
    if vrsta_strojev == 'Preizkus tesnosti' and tagname_tim == 'mopf':
        return df
    
    elif vrsta_strojev == 'Preizkus tesnosti' and tagname_tim == 'stellantis':
        return df
    
    elif vrsta_strojev == 'Preizkus tesnosti' and tagname_tim == 'heat_soba':
        return df
    
    elif vrsta_strojev == 'Preizkus tesnosti' and tagname_tim == 'stellantis':
        return df
    
    else:
        return df
    

def adjust_for_pranje(df, vrsta_strojev, tagname_tim, list_of_machines):
    if tagname_tim == 'stellantis':
        if vrsta_strojev == 'Pranje 1':
            return df
    
        elif vrsta_strojev == 'HPWD + Pranje 2':
            return df
    
        elif vrsta_strojev == 'HPWD + Pranje 2':
            return df
        
        else:
            return df
    
    else:
        # Filter rows where 'Opravilo' is '2240'
        df_2240 = df[df['Opravilo'] == '2240']
        
        # Convert 'Operacija' to numeric type
        df_2240['Operacija'] = pd.to_numeric(df_2240['Operacija'], errors='coerce')
        
        # Sort values by 'Opravilo' and 'Operacija'
        df_2240_sorted = df_2240.sort_values(by=['Opravilo', 'Operacija'])
        # try:
            # Drop duplicates based on 'Artikel', 'Stroj', 'Opravilo', 'Operacija' for 'Opravilo' 2240
        filter_duplicate_cols = [x for x in ['Artikel', 'Stroj', 'Opravilo','Izmena','Delovno mesto','Postaja', 'Dnevni datum'] if x in df_2240_sorted]
        df_2240_filtered = df_2240_sorted.drop_duplicates(subset=filter_duplicate_cols, keep='first')
        # except:
        #     breakpoint()
        #     pass
        
        # Concatenate filtered 'Opravilo' 2240 DataFrame with the rest of the DataFrame
        final_df = pd.concat([df_2240_filtered, df[df['Opravilo'] != '2240']])
        final_df['Operacija'] = final_df['Operacija'].astype(str)
        # breakpoint()
        
        return final_df
    
def fill_postaja_based_on_max(df, provided_max_postaja=None):
    """
    Fills the 'Postaja' column for rows where 'Izmet celice' is 0 with the highest 'Postaja'
    for the same 'Stroj', 'Operacija', and 'Artikel' combination where 'Kolicina celice' > 0.

    Parameters:
    df (DataFrame): The input pandas DataFrame containing columns 'Stroj', 'Operacija', 'Artikel', 'Postaja', 'Izmet celice', and 'Kolicina celice'.
    provided_max_postaja (dict, DataFrame, or None): An optional parameter that can be a dictionary mapping combinations of 'Stroj', 'Operacija', 'Artikel'
                                                     to their corresponding 'Max_Postaja', a DataFrame with these values, or None.
                                                     If not provided, the maximum 'Postaja' will be computed from the data.

    Returns:
    DataFrame: A DataFrame with the updated 'Postaja' values.
    """
    
    df_numeric = df.copy()
    df_numeric['Postaja'] = pd.to_numeric(df_numeric['Postaja'], errors='coerce')
    
    # Step 1: Compute the max_postaja DataFrame using groupby
    max_postaja = (
        df_numeric[df_numeric['Kolicina celice'] > 0]
        .groupby(['Stroj', 'Operacija', 'Artikel'])['Postaja']
        .max()
        .reset_index()
        .rename(columns={'Postaja': 'Max_Postaja'})
    )

    # Step 2: If provided_max_postaja is supplied, replace the computed values
    if provided_max_postaja is not None:
        if isinstance(provided_max_postaja, dict):
            # Convert the dictionary to a DataFrame format similar to max_postaja
            provided_max_postaja = pd.DataFrame([
                {'Stroj': k[0], 'Operacija': k[1], 'Artikel': k[2], 'Max_Postaja': v}
                for k, v in provided_max_postaja.items()
            ])
        elif isinstance(provided_max_postaja, pd.DataFrame):
            # Ensure provided_max_postaja is structured correctly
            required_columns = {'Stroj', 'Operacija', 'Artikel', 'Max_Postaja'}
            if not required_columns.issubset(provided_max_postaja.columns):
                raise ValueError("provided_max_postaja DataFrame must contain columns: ['Stroj', 'Operacija', 'Artikel', 'Max_Postaja']")
        else:
            raise ValueError("provided_max_postaja must be a DataFrame or a dictionary.")

        # Merge provided_max_postaja with computed max_postaja to update values
        max_postaja = max_postaja.merge(provided_max_postaja, on=['Stroj', 'Operacija', 'Artikel'], how='left', suffixes=('', '_provided'))
        # Replace computed values with provided ones if they exist
        max_postaja['Max_Postaja'] = max_postaja['Max_Postaja_provided'].combine_first(max_postaja['Max_Postaja'])
        max_postaja.drop(columns=['Max_Postaja_provided'], inplace=True)

    # Step 3: Merge the maximum Postaja values back to the original DataFrame
    df = df.merge(max_postaja, on=['Stroj', 'Operacija', 'Artikel'], how='left')

    # Step 4: Fill missing 'Postaja' values where 'Izmet celice' is 0
    df.loc[(df['Izmet celice'] > 0)&(df['Postaja'].isna()&(df['Kolicina celice'] == 0)), 'Postaja'] = df['Max_Postaja']

    # Step 5: Drop the auxiliary column
    df.drop(columns=['Max_Postaja'], inplace=True)

    return df

def adjust_for_pregledovanje_2150_filter_postaja(df, vrsta_strojev, tagname_tim, list_of_machines):
        
    if tagname_tim == 'stellantis':
        df = fill_postaja_based_on_max(df)
        df['Postaja'] = pd.to_numeric(df['Postaja'], errors='coerce').fillna('')
        if vrsta_strojev == 'Obdelava':
            df = df[df['Operacija'].isin(['40', 40])]
            condition_ta631 = (df['Stroj'] == 'TA631') & (df['Postaja'].isin([601]))
            condition_ta632 = (df['Stroj'] == 'TA632') & (df['Postaja'].isin([603]))
            
            # Combine the conditions using logical OR to keep rows matching either condition
            df = df[condition_ta631 | condition_ta632]
            
            return df.reset_index(drop=True).fillna('')
        
        elif vrsta_strojev == 'HPWD + Pranje':
            condition_T3001 = (df['Stroj'] == 'T3001') & (df['Operacija'].isin([50, '50']))
            condition_T3401 = (df['Stroj'] == 'T3401') & (df['Operacija'].isin([55, '55']))
            
            # # Combine the conditions using logical OR to keep rows matching either condition
            df = df[condition_T3001 | condition_T3401]
            # breakpoint()
            
            return df.reset_index(drop=True).fillna('')
        
        elif vrsta_strojev == 'Montaža 1':

            df = df[df['Operacija'].isin(['60', 60])]
            # df['Postaja'] = pd.to_numeric(df['Postaja'], errors='coerce')

            # Define conditions for 'Stroj' TA631 and TA632
            # condition = (df['Stroj'] == 'TMA21') & (df['Postaja'].isin([30, '', np.nan]))
            condition = (df['Stroj'] == 'TMA21') & (df['Postaja'].isin([30]))
            # breakpoint()
            # Combine the conditions using logical OR to keep rows matching either condition
            df = df[condition]
            
            return df.reset_index(drop=True).fillna('')
        
        elif vrsta_strojev == 'Montaža 2 + PT':
            # breakpoint()
            df = df[df['Operacija'].isin(['70', 70])]
            # df['Postaja'] = pd.to_numeric(df['Postaja'], errors='coerce')

            # Define conditions for 'Stroj' TA631 and TA632
            condition = (df['Stroj'] == 'TMB22') & (df['Postaja'].isin([20]))
            
            # Combine the conditions using logical OR to keep rows matching either condition
            df = df[condition]
            
            return df.reset_index(drop=True).fillna('')
        
        elif vrsta_strojev == 'Vizualna kontrola LTH':

            df = df[df['Operacija'].isin(['70', 70])]
            # df['Postaja'] = pd.to_numeric(df['Postaja'], errors='coerce')

            # Define conditions for 'Stroj' TA631 and TA632
            condition = (df['Stroj'] == 'TMB22') & (df['Postaja'].isin([30, 40]))
            
            # Combine the conditions using logical OR to keep rows matching either condition
            df = df[condition]
            
            return df.reset_index(drop=True).fillna('')
        
        elif vrsta_strojev == 'Firewall':
            # breakpoint()
            df = df[df['Operacija'].isin(['70', 70])]
            # df['Postaja'] = pd.to_numeric(df['Postaja'], errors='coerce')

            # Define conditions for 'Stroj' TA631 and TA632
            condition = (df['Stroj'] == 'TMB22') & (df['Postaja'].isin([50]))
            
            # Combine the conditions using logical OR to keep rows matching either condition
            df = df[condition]
            
            return df.reset_index(drop=True).fillna('')
        
        elif vrsta_strojev == 'Embaliranje':
            df = df[df['Operacija'].isin(['80', 80])]
            return df.reset_index(drop=True).fillna('')
    elif tagname_tim == 'onebox':
        if vrsta_strojev == 'Pregledovanje':
            return df.reset_index(drop=True).fillna('')
        elif vrsta_strojev == 'Firewall':
            return df.reset_index(drop=True).fillna('')
        
        elif vrsta_strojev == 'Preizkus tesnosti':
            return df.reset_index(drop=True).fillna('')

    elif vrsta_strojev == 'Pregledovanje' and tagname_tim == 'bosch__audi':
        df_2150 = df[df['Opravilo'].isin(['2150'])].reset_index(drop=True)
        return df_2150
    
    
    elif vrsta_strojev == 'Impregnacija' and tagname_tim == 'mopf':
        # breakpoint()
        condition_tg601 = df['Stroj'] == 'TG601'
        condition_postaja_50 = df['Opravilo'] == '2907'
        mask = ~condition_tg601 | (condition_tg601 & condition_postaja_50)
        df = df[mask]
        return df
    
    return df

def adjust_for_pregledovanje(df, vrsta_strojev, tagname_tim, list_of_machines, adjust_for_pregledovanje_TRUE=True):

    if adjust_for_pregledovanje_TRUE:
        # breakpoint()
        if (vrsta_strojev == 'Pregledovanje' and tagname_tim == 'heat_soba') or (vrsta_strojev == 'Preizkus tesnosti' and tagname_tim == 'heat_soba'):
            # breakpoint()
            if (vrsta_strojev == 'Preizkus tesnosti' and tagname_tim == 'heat_soba'):

                condition = df['Delovno mesto'].eq('S10')
                df.loc[condition, 'Stroj'] = 'S10'
                
                try:
                    plan_mapping = df.dropna(subset=['Plan']).groupby('Artikel')['Plan'].first().to_dict()
                except:
                    plan_mapping = {}
                    
                for idx, row in df[condition].iterrows():
                    if row['Artikel'] in plan_mapping:
                        df.at[idx, 'Plan'] = plan_mapping[row['Artikel']]
                        
                
            else:
                artikel_values = df[df['Stroj'].isin(list_of_machines)]['Artikel'].unique()
        
                if len(artikel_values) == 0:
                    artikel_values = df[df['Delovno mesto'].isin(list_of_machines)]['Artikel'].unique()
                
                try:
                    plan_mapping = df[df['Stroj'].isin(list_of_machines)].dropna(subset=['Plan']).groupby('Artikel')['Plan'].first().to_dict()
                except:
                    plan_mapping = {}
                
                # df = df[~df['Stroj'].isin(list_of_machines)]
                
                condition = df['Delovno mesto'].eq('S10') & df['Artikel'].isin(artikel_values)
                
                df.loc[condition, 'Stroj'] = 'S10'
                
                for idx, row in df[condition].iterrows():
                    if row['Artikel'] in plan_mapping:
                        df.at[idx, 'Plan'] = plan_mapping[row['Artikel']]
                    
            # df = df[df['Delovno mesto'].isin(['S10'])].reset_index(drop=True)
                    
        if vrsta_strojev == 'Pregledovanje' and tagname_tim == 'stellantis':
            pass
                        
        elif vrsta_strojev == 'Pregledovanje' and tagname_tim == 'onebox':
            delovna_mesta = ['S10', 'S09', 'S08', 'S07', 'S15', 'G15']
            for delovno_mesto in delovna_mesta:
                # breakpoint()
                artikel_values = list(df[df['Stroj'].isin(list_of_machines)]['Artikel'].unique()) + list(df[df['Delovno mesto'].isin(list_of_machines)]['Artikel'].unique())
        
                if len(artikel_values) == 0:
                    artikel_values = df[df['Delovno mesto'].isin(list_of_machines)]['Artikel'].unique()
                
                try:
                    plan_mapping = df[df['Stroj'].isin(list_of_machines)].dropna(subset=['Plan']).groupby('Artikel')['Plan'].first().to_dict()
                except:
                    plan_mapping = {}
                
                # df = df[~df['Stroj'].isin(list_of_machines)]
                
                condition = df['Delovno mesto'].eq(delovno_mesto) & df['Artikel'].isin(artikel_values)
                
                df.loc[condition, 'Stroj'] = delovno_mesto
                
                for idx, row in df[condition].iterrows():
                    if row['Artikel'] in plan_mapping:
                        df.at[idx, 'Plan'] = plan_mapping[row['Artikel']]
                        
        elif vrsta_strojev == 'Firewall' and tagname_tim == 'onebox':
            # breakpoint()
            delovna_mesta = ['S10', 'S09', 'S08', 'S07', 'S15', 'G15', 'S20']
            for delovno_mesto in delovna_mesta:
                # breakpoint()
                artikel_values = list(df[df['Stroj'].isin(list_of_machines)]['Artikel'].unique()) + list(df[df['Delovno mesto'].isin(list_of_machines)]['Artikel'].unique())
        
                if len(artikel_values) == 0:
                    artikel_values = df[df['Delovno mesto'].isin(list_of_machines)]['Artikel'].unique()
                
                try:
                    plan_mapping = df[df['Stroj'].isin(list_of_machines)].dropna(subset=['Plan']).groupby('Artikel')['Plan'].first().to_dict()
                except:
                    plan_mapping = {}
                
                # df = df[~df['Stroj'].isin(list_of_machines)]
                
                condition = df['Delovno mesto'].eq(delovno_mesto) & df['Artikel'].isin(artikel_values)
                
                # df.loc[condition, 'Stroj'] = delovno_mesto
                
                for idx, row in df[condition].iterrows():
                    if row['Artikel'] in plan_mapping:
                        df.at[idx, 'Plan'] = plan_mapping[row['Artikel']]
                        
                # df = df[df['Delovno mesto'].isin(delovna_mesta)].reset_index(drop=True)
                        
        elif vrsta_strojev == 'Pregledovanje' and tagname_tim == 'bosch__audi':
            delovna_mesta = ['S10']
            for delovno_mesto in delovna_mesta:
                # breakpoint()
                artikel_values = df[df['Stroj'].isin(list_of_machines)]['Artikel'].unique()
        
                if len(artikel_values) == 0:
                    artikel_values = df[df['Delovno mesto'].isin(list_of_machines)]['Artikel'].unique()
                
                try:
                    plan_mapping = df[df['Stroj'].isin(list_of_machines)].dropna(subset=['Plan']).groupby('Artikel')['Plan'].first().to_dict()
                except:
                    plan_mapping = {}
            
                
                condition = df['Delovno mesto'].eq(delovno_mesto) & df['Artikel'].isin(artikel_values)
                
                df.loc[condition, 'Stroj'] = delovno_mesto
                
                for idx, row in df[condition].iterrows():
                    if row['Artikel'] in plan_mapping:
                        df.at[idx, 'Plan'] = plan_mapping[row['Artikel']]

                                
    return df


def main_transformation(df, vrsta_strojev, tagname_tim, list_of_machines, adjust_for_pregledovanje_TRUE=True):
    df = filter_stroj_postaja(df, vrsta_strojev, tagname_tim)
    df = adjust_for_preizkus_tesnosti(df, vrsta_strojev, tagname_tim)
    df = adjust_for_pregledovanje(df, vrsta_strojev, tagname_tim, list_of_machines, adjust_for_pregledovanje_TRUE)
    return df

def fetch_realizacija_proizvodnje_zaposleni(start_date_object, end_date_object, list_of_machines):
    # External reporting DB URL
    DATABASE_URL = os.getenv('EXTERNAL_DATABASE_URL', f"postgresql://postgres:postgres@{server_domain}:5432/external_db")

    engine = create_engine(DATABASE_URL)

    with engine.connect() as connection:
        # Use a simple query
        fetch_query = text("""
            SELECT "Dnevni datum", "Stroj", "Artikel", "Izmena", "Delovno mesto", "Zaposleni", "Ime zaposlenega"
            FROM realizacija_proizvodnje_zaposleni 
            WHERE "Dnevni datum" BETWEEN :start_date AND :end_date
            AND "Stroj" = ANY(:machines)
        """)

        result = connection.execute(fetch_query, {
            "start_date": start_date_object,
            "end_date": end_date_object,
            "machines": list_of_machines
        })

        data = result.fetchall()
        return pd.DataFrame(data)

def update_planirano_delovanje_strojne_ure(data_df_agg, vrsta_strojev):
    # Get today's date in the correct format (only date part)
    today_date = datetime.today().date()
    
    # Define the reference time (6:00 AM today)
    reference_time = datetime.combine(today_date, datetime.min.time()) + timedelta(hours=6)
    
    # Calculate the current time
    current_time = datetime.now()

    # Calculate the hours passed since 6:00 AM
    hours_passed = (current_time - reference_time).total_seconds() / 3600
    
    # Ensure hours_passed is non-negative (in case the current time is before 6:00 AM)
    hours_passed = max(0, hours_passed - 1)
    
    # Convert 'Dnevni datum' to date format for comparison
    today_mask = data_df_agg['Dnevni datum'].dt.date == today_date
    
    # breakpoint()

    # Update 'Planirano_delovanje_strojne_ure' only for rows with today's date
    try:
        data_df_agg.loc[today_mask, 'Planirano_delovanje_strojne_ure'] = np.round(hours_passed,decimals=1)
    except:
        data_df_agg.loc[today_mask, 'Planirano_delovanje_strojne_ure'] = 0
        
        
    data_df_agg.loc[~today_mask, 'Planirano_delovanje_strojne_ure'] = 24
    
    return data_df_agg

def add_dtm_cols_to_df(df,column_datum):
    datumi_fixed = [datetime.strptime(x, '%d.%m.%Y') if type(x) ==str else x for x in df[column_datum].values]
    df[column_datum] = datumi_fixed
    df[column_datum] = pd.to_datetime(df[column_datum], format='%Y-%m-%d %H:%M:%S')
    df['Leto'] = pd.DatetimeIndex(df[column_datum]).year
    df['Teden'] =(df[column_datum]).dt.isocalendar().week
    df['Leto_Mesec'] = df[column_datum].apply(lambda x: x.strftime('%Y-%m')) 
    df['Leto_Mesec'] = pd.to_datetime(df['Leto_Mesec'], format='%Y-%m')
    df['Teden'] = df['Teden'].apply(lambda x: str(x).zfill(2)) 
    df['Leto_Teden'] = df['Leto'].astype(str) +'_'+df['Teden'].astype(str)
    df['Dan'] = pd.DatetimeIndex(df[column_datum]).day
    df['Dan'] = [dnevi_dict_full[x.weekday()] for x in df[column_datum].dt.date]
    # df.drop('Teden', inplace=True, axis=1)
    return df

# date_obj = f"d3.timeParse('%Y-%m-%dT%H:%M:%S')(params.data.{x})"
def safe_int_label(value):
    try:
        numeric_value = pd.to_numeric(value, errors='coerce')
        if pd.isnull(numeric_value):
            return '0', 0
        else:
            try:
                return str(int(numeric_value)), int(np.round(numeric_value, decimals=1))
            except:
                return '0', 0
            
    except (ValueError, TypeError):
        return '0', 0
    
def fetch_plan_bulk_dropdown(stroj_artikel_pairs, vrsta_strojev, engine):
    """
    Fetches all combinations (or pairs) of stroj and artikel where stroj can be in 'Stroj', 'Sklop', or 'Ser. artikel'
    and artikel matches 'Artikel'. Also filters by 'Opravilo' based on vrsta_strojev.
    
    :param stroj_artikel_pairs: List of tuples containing (stroj, artikel) pairs to filter.
    :param vrsta_strojev: The type of machine ('vrsta_strojev') to filter and map to 'Opravilo'.
    :param engine: SQLAlchemy engine for connecting to the database.
    :return: List of tuples containing filtered stroj_artikel pairs.
    """
    try:
        # Prepare the WHERE clause to filter based on the stroj in 'Stroj', 'Sklop', 'Ser. artikel' and artikel in 'Artikel'
        conditions = " OR ".join([
            f"('{stroj}' IN (\"Stroj\", \"Sklop\", \"Ser. artikel\") AND \"Artikel\" = '{artikel}')"
            for stroj, artikel in stroj_artikel_pairs
        ])
        
        
        # SQL query to fetch stroj_artikel pairs, including the 'Opravilo' condition
        query = f"""
        SELECT DISTINCT
            "Stroj", "Sklop", "Ser. artikel", "Zap_ope", "Operacija", "Opravilo", "Artikel", "Norma (dan)", "Proizvodni tempo (kos/uro)", "Cycle Time mins"
        FROM plan_norme_tirou1402
        WHERE ({conditions})
        """
        
        # Parameters for the query
        
        # Execute the query with the correct parameters
        with engine.connect() as connection:
            fetched_pairs = connection.execute(text(query)).fetchall()
        
        # Convert the fetched pairs to a DataFrame and return
        return pd.DataFrame(fetched_pairs)

    except Exception as e:
        print(f"Error fetching data: {e}")
        return None
    
    
def assign_plan_teden_and_st_izm(data_df, stroj_artikel_pairs, week, engine):
    try:
        fetched_data_dict = fetch_recent_plan_izm_bulk(stroj_artikel_pairs, week, engine)

        for index, row in data_df.iterrows():
            key = (row['Stroj'], row['Artikel'])

            # Check if the key exists in fetched_data_dict
            if key in fetched_data_dict:
                # Extract values from fetched_data_dict
                plan_value, st_izm_value, _ = fetched_data_dict[key]

                # Update Plan, Št. izm values from fetched_data_dict
                data_df.at[index, 'Plan, teden'] = plan_value
                data_df.at[index, 'Št. izm'] = st_izm_value if st_izm_value else '3'

            # If key is not in fetched_data_dict, default Št. izm to 3
            else:
                data_df.at[index, 'Št. izm'] = '3'

    except Exception as e:
        print(f"Error: {e}")
        data_df['Št. izm'] = '3'
        
    return data_df

def build_stroj_artikel_pairs(data_df):
    stroj_artikel_pairs = []
    for _, row in data_df.iterrows():
        stroj = row['Stroj']
        artikel = row['Artikel']
        postaja = row['Postaja'] if 'Postaja' in row and pd.notna(row['Postaja']) and row['Postaja'] != '' else None
        
        # Replace 'Stroj' with 'Postaja' when conditions are met
        # if (stroj.startswith('TR') or stroj.startswith('TP')) and postaja:
        if stroj.startswith('TR') and postaja:
            stroj = postaja  # Use 'Postaja' as 'Stroj' for querying
        
        stroj_artikel_pairs.append((stroj, artikel))
    
    # Remove duplicates and sort
    unique_stroj_artikel_pairs = list(set(stroj_artikel_pairs))
    unique_stroj_artikel_pairs.sort()
    return unique_stroj_artikel_pairs

def assign_plan_tehnoloski_tirou(data_df, stroj_artikel_pairs, vrsta_strojev, engine, for_OEE):
    # breakpoint()
    # if vrsta_strojev == 'Obdelava':
    #     if not for_OEE:
    #         breakpoint()
    try:
        fetched_plan_options_df = fetch_plan_bulk_dropdown_drop_duplicates(stroj_artikel_pairs, vrsta_strojev, engine)
        fetched_plan_options_df['Norma (dan)'] = pd.to_numeric(fetched_plan_options_df['Norma (dan)'], errors='coerce')
        
        for index, row in data_df.iterrows():
            # if not for_OEE:
            #     if row['Stroj'] == 'TR301':
            #         breakpoint()
            # Check if fetched_plan_options_df has corresponding data
            if not fetched_plan_options_df.empty:
                # Filter based on Stroj and Artikel
                filtered_fetched_plan_options_df = fetched_plan_options_df[(fetched_plan_options_df['Stroj'] == row['Stroj'])&(fetched_plan_options_df['Artikel'] == row['Artikel'])]

                # If there's a match, update the Plan from fetched_plan_options_df
                if filtered_fetched_plan_options_df.empty:
                    filtered_fetched_plan_options_df = fetched_plan_options_df[(fetched_plan_options_df['Sklop'] == row['Stroj'])&(fetched_plan_options_df['Artikel'] == row['Artikel'])]
                
                if not filtered_fetched_plan_options_df.empty:
                    plan_value_from_options = filtered_fetched_plan_options_df['Norma (dan)'].values[0]
                    data_df.at[index, 'Plan'] = plan_value_from_options

    except Exception as e:
        print(f"Error: {e}")
        
    return data_df

# def fetch_plan_bulk_dropdown_drop_duplicates(stroj_artikel_pairs, vrsta_strojev, engine):
#     try:
#         if not stroj_artikel_pairs:
#             return pd.DataFrame()
        
#         queries = [
#             " OR ".join([
#                 f"('Stroj' LIKE '%{stroj}%' OR \"Sklop\" LIKE '%{stroj}%' OR \"Ser. artikel\" LIKE '%{stroj}%') AND \"Artikel\" = '{artikel}'"
#                 for stroj, artikel in stroj_artikel_pairs
#             ]),
#             " OR ".join([
#                 f"('Stroj' LIKE '%{stroj}%' AND \"Artikel\" = '{artikel}'"
#                 for stroj, artikel in stroj_artikel_pairs
#             ]),
#             " OR ".join([
#                 f"((\"Sklop\" LIKE '%{stroj}%' OR \"Ser. artikel\" LIKE '%{stroj}%') AND \"Artikel\" = '{artikel}'"
#                 for stroj, artikel in stroj_artikel_pairs
#             ])
#         ]

#         for conditions in queries:
#             if vrsta_strojev == 'Pregledovanje':
#                 query = f"""
#                 SELECT sub.*
#                 FROM (
#                     SELECT
#                         "Stroj", "Sklop", "Ser. artikel", "Zap_ope", "Operacija", "Opravilo", "Artikel",
#                         "Norma (dan)", "Proizvodni tempo (kos/uro)", "Cycle Time mins",
#                         ROW_NUMBER() OVER (PARTITION BY "Stroj", "Artikel" ORDER BY "Operacija"::integer ASC) as rn
#                     FROM plan_norme_tirou1402
#                     WHERE ({conditions}) AND "Operacija"::integer > 45
#                 ) sub
#                 WHERE sub.rn = 1
#                 """
#             else:
#                 query = f"""
#                 SELECT DISTINCT ON ("Stroj", "Zap_ope", "Operacija", "Opravilo", "Artikel", "Norma (dan)", "Proizvodni tempo (kos/uro)", "Cycle Time mins")
#                     "Stroj", "Sklop", "Ser. artikel", "Zap_ope", "Operacija", "Opravilo", "Artikel", "Norma (dan)", "Proizvodni tempo (kos/uro)", "Cycle Time mins"
#                 FROM plan_norme_tirou1402
#                 WHERE ({conditions})
#                 """
#             params = {}
            
#             with engine.connect() as connection:
#                 result = connection.execute(text(query), params)
#                 columns = result.keys()
#                 fetched_pairs = result.fetchall()
                
#             if fetched_pairs:
#                 fetched_pairs_df = pd.DataFrame(fetched_pairs, columns=columns)
#                 return fetched_pairs_df
        
#         return pd.DataFrame()

#     except Exception as e:
#         print(f"Error fetching data: {e}")
#         return pd.DataFrame()

def fetch_plan_bulk_dropdown_drop_duplicates(stroj_artikel_pairs, vrsta_strojev, engine):
    try:
        if not stroj_artikel_pairs:
            return pd.DataFrame()
        
        # conditions = " OR ".join([
        #     f"('{stroj}' IN (\"Stroj\", \"Sklop\", \"Ser. artikel\") AND \"Artikel\" = '{artikel}')"
        #     for stroj, artikel in stroj_artikel_pairs
        # ])
        
        conditions = " OR ".join([
            f"('Stroj' LIKE '%{stroj}%' OR \"Sklop\" LIKE '%{stroj}%' OR \"Ser. artikel\" LIKE '%{stroj}%') AND \"Artikel\" = '{artikel}'"
            for stroj, artikel in stroj_artikel_pairs
        ])

        
        if vrsta_strojev == 'Pregledovanje':
            query = f"""
            SELECT sub.*
            FROM (
                SELECT
                    "Stroj", "Sklop", "Ser. artikel", "Zap_ope", "Operacija", "Opravilo", "Artikel",
                    "Norma (dan)", "Proizvodni tempo (kos/uro)", "Cycle Time mins",
                    ROW_NUMBER() OVER (PARTITION BY "Stroj", "Artikel" ORDER BY "Operacija"::integer ASC) as rn
                FROM plan_norme_tirou1402
                WHERE ({conditions}) AND "Operacija"::integer > 45
            ) sub
            WHERE sub.rn = 1
            """
            params = {}
        else:
            query = f"""
            SELECT DISTINCT ON ("Stroj", "Zap_ope", "Operacija", "Opravilo", "Artikel", "Norma (dan)", "Proizvodni tempo (kos/uro)", "Cycle Time mins")
                "Stroj", "Sklop", "Ser. artikel", "Zap_ope", "Operacija", "Opravilo", "Artikel", "Norma (dan)", "Proizvodni tempo (kos/uro)", "Cycle Time mins"
            FROM plan_norme_tirou1402
            WHERE ({conditions})
            """
            params = {}
        
        with engine.connect() as connection:
            result = connection.execute(text(query), params)
            columns = result.keys()
            fetched_pairs = result.fetchall()
        
        if fetched_pairs:
            fetched_pairs_df = pd.DataFrame(fetched_pairs, columns=columns)
            return fetched_pairs_df
        else:
            return pd.DataFrame()

    except Exception as e:
        print(f"Error fetching data: {e}")
        return pd.DataFrame()

def fetch_machine_data(vrsta_strojev, identifier, start_date_object, end_date_object, 
                        week, tagname_tim, radios_dtm, pathname, data_dict, 
                        data_kontrolni_list_dict, data_zadnji_nalog_dict, data_dict_sum, 
                        data_dict_po_izmenah, data_dict_po_postajah, data_dict_po_izmenah_tooltip_dict, 
                        data_dict_po_izmenah_zaposleni_tooltip_dict, data_planirane_kolicine_dict,
                        vsi_artikli, for_OEE = False, machines_to_include = []):
    """
    Fetches machine data for a given team and machine type.

    Parameters:
    - vrsta_strojev: Type of machine (e.g., 'Obdelava')
    - start_date_object: Start date (datetime object)
    - end_date_object: End date (datetime object)
    - tagname_tim: Team name (e.g., 'HEAT Obdelava')
    - radios_dtm: Time granularity ('D', 'M', 'T')
    - machines_to_include: Optional list of machines to include

    Returns:
    - data_df: Pandas DataFrame with the fetched data
    """

    # Step 1: Fetch the list of machines for the given team and machine type
    try:
        tim_config = TimConfig.objects.get(team_name=tagname_tim)
        tim_definitions = TimDefinition.objects.filter(tim_config=tim_config, ime_tabele=vrsta_strojev)
        stroj_entries = StrojEntry.objects.filter(tim_definition__in=tim_definitions)
        list_of_machines = list(stroj_entries.values_list('stroj', flat=True).distinct())
    except TimConfig.DoesNotExist:
        list_of_machines = []
    
    # Override with machines_to_include if provided
    if machines_to_include:
        list_of_machines = machines_to_include

    # If no machines found, return None
    if not list_of_machines:
        return None

    # Step 2: Define date column based on radios_dtm
    if radios_dtm == 'D':
        date_column_sql = '"Dnevni datum"'
        date_column = 'Dnevni datum'
        date_column_aux = 'Dan'
    elif radios_dtm == 'M':
        date_column_sql = "date_trunc('month', \"Dnevni datum\")::date AS \"Dnevni datum\""
        date_column = 'Leto_Mesec'
        date_column_aux = 'Mesec'
    elif radios_dtm == 'T':
        date_column_sql = "date_trunc('week', \"Dnevni datum\")::date AS \"Dnevni datum\""
        date_column = 'Leto_Teden'
        date_column_aux = 'Leto_Teden'
    else:
        date_column_sql = '"Dnevni datum"'
        date_column = 'Dnevni datum'
        date_column_aux = 'Dan'

    # Step 3: Construct the SQL query
    query_parts = [
        f'''SELECT "Artikel", {date_column_sql}, "Stroj", "Postaja", "Operacija", "Opravilo", "Izmena", "Delovno mesto",
        SUM("Kolicina celice") as "Kolicina celice", SUM("Izmet celice") as "Izmet celice"
        FROM realizacija_proizvodnje_postaje_opravila 
        WHERE "Dnevni datum" BETWEEN %(start_date)s AND %(end_date)s'''
    ]

    query_parts.append("\"Stroj\" IN %(machines)s")
    final_query = " AND ".join(query_parts)
    final_query += f' GROUP BY "Artikel", "Dnevni datum", "Stroj", "Postaja", "Operacija", "Opravilo", "Izmena", "Delovno mesto"'

    params = {
        'start_date': start_date_object,
        'end_date': end_date_object,
        'machines': tuple(list_of_machines),
    }

    # Step 4: Execute the query using the external database connection
    with connections['external_db'].cursor() as cursor:
        cursor.execute(final_query, params)
        columns = [col[0] for col in cursor.description]
        data = cursor.fetchall()
        data_df = pd.DataFrame(data, columns=columns)

    # Adjust data types
    data_df['Kolicina celice'] = pd.to_numeric(data_df['Kolicina celice'], errors='coerce').fillna(0)
    data_df['Izmet celice'] = pd.to_numeric(data_df['Izmet celice'], errors='coerce').fillna(0)
    data_df['Delovno mesto'] = data_df['Delovno mesto'].fillna('').astype(str)

    if 'pranje' in vrsta_strojev.lower():
        data_df = adjust_for_pranje(data_df, vrsta_strojev, tagname_tim, list_of_machines)
    data_df = adjust_for_pregledovanje_2150_filter_postaja(data_df, vrsta_strojev, tagname_tim, list_of_machines)
    
    # Assign plan
    data_df['Plan'] = 0
    unique_stroj_artikel_pairs = build_stroj_artikel_pairs(data_df)
    data_df = assign_plan_tehnoloski_tirou(data_df, unique_stroj_artikel_pairs, vrsta_strojev, engine, for_OEE)
    
    data_df['Kos/uro'] = data_df['Plan']/24
    data_df['Plan'] = pd.to_numeric(data_df['Plan'], errors='coerce').round(decimals=0).fillna(0)
    data_df['Plan'] = data_df['Plan'].replace([np.inf, -np.inf], np.nan)
    
    # if not for_OEE:
    #     breakpoint()
    
    data_df = add_dtm_cols_to_df(data_df,'Dnevni datum')
    
    data_dict_po_izmenah[vrsta_strojev] = data_df.copy()
    
    # Continue with rest of the code
    
    # Fetch planirano_delovanje_str_art_dan
    if os.name == 'nt':
        DATABASE_URL = os.getenv('EXTERNAL_DATABASE_URL', f"postgresql://postgres:postgres@{server_domain}:5432/external_db")
        # DATABASE_URL = os.getenv('EXTERNAL_DATABASE_URL', "postgresql://postgres:postgres@localhost:5432/external_db")
    else:
        DATABASE_URL = os.getenv('EXTERNAL_DATABASE_URL', "postgresql://postgres:postgres@postgres:5432/external_db")
    engine = create_engine_postgres_pool(DATABASE_URL)
    query_parts = ["SELECT * FROM planirano_delovanje_str_art_dan WHERE \"Dnevni datum\" BETWEEN :start_date AND :end_date"]
    if list_of_machines:
        query_parts.append("\"Stroj\" = ANY(:machines)")
    final_query = " AND ".join(query_parts)
    params = {
        'start_date': start_date_object,
        'end_date': end_date_object
    }
    if list_of_machines:
        params['machines'] = list_of_machines
    if machines_to_include:
        params['machines'] = list_of_machines
        list_of_machines = machines_to_include
    df_planirano_delovanje_groupby = pd.read_sql_query(text(final_query), con=engine, params=params)
    df_planirano_delovanje_groupby['Artikel'].replace('', np.nan, inplace=True)
    df_planirano_delovanje_groupby = df_planirano_delovanje_groupby.dropna(subset=['Artikel']).set_index(['Stroj','Artikel' ,'Dnevni datum'])
    if (vrsta_strojev == 'Pregledovanje' or vrsta_strojev == 'Peskanje' or vrsta_strojev == 'Firewall') or (vrsta_strojev == 'Preizkus tesnosti' and tagname_tim == 'heat_soba') or (vrsta_strojev == 'Litje' and identifier == '_bosch'):
        # breakpoint()
        if (tagname_tim == 'stellantis' or tagname_tim == 'onebox') or (vrsta_strojev == 'Litje' and identifier == '_bosch'):
            artikli_list = variables[f'lean_timi_excel{identifier}'][variables[f'lean_timi_mapping{identifier}'][tagname_tim]]['Artikli'].dropna().astype(str).str.replace('.0','').unique()
            artikli_list = ['0' + x for x in artikli_list if not x[0]=='0']
            vsi_artikli_na_teh_strojih = artikli_list
            data_df = data_df[data_df['Artikel'].isin(artikli_list)].reset_index(drop=True)
        else:
            vsi_stroji_za_kode_za_pregledovanje = variables[f'vsi_stroji_po_teamih{identifier}'][variables[f'lean_timi_mapping{identifier}'][tagname_tim]]
            vsi_stroji_za_kode_za_pregledovanje = [x for x in vsi_stroji_za_kode_za_pregledovanje if not str(x)[0] == 'S']
            if vsi_stroji_za_kode_za_pregledovanje:
                params['machines'] = vsi_stroji_za_kode_za_pregledovanje
            data_df_pregledovanje = pd.read_sql_query(text(final_query), con=engine, params=params)
            mask = (data_df_pregledovanje['Dnevni datum'] >= start_date_object) & (data_df_pregledovanje['Dnevni datum'] <= end_date_object)
            data_df_pregledovanje = data_df_pregledovanje.loc[mask]
            vsi_artikli_na_teh_strojih = data_df_pregledovanje[data_df_pregledovanje['Stroj'].isin(vsi_stroji_za_kode_za_pregledovanje)]['Artikel'].unique().tolist()
    
    
    if (vrsta_strojev == 'Preizkus tesnosti' and tagname_tim == 'heat_soba'):
        adjust_for_pregledovanje_TRUE = False
    else:
        adjust_for_pregledovanje_TRUE = True
        

    data_df = main_transformation(data_df, vrsta_strojev, tagname_tim, list_of_machines, adjust_for_pregledovanje_TRUE)
    if vrsta_strojev == 'Pregledovanje':
        # breakpoint()
        if tagname_tim == 'stellantis' or tagname_tim == 'onebox':
            pass
        elif tagname_tim == 'heat_soba':
            artikli_list = variables[f'lean_timi_excel{identifier}'][variables[f'lean_timi_mapping{identifier}'][tagname_tim]]['Artikli'].dropna().astype(str).str.replace('.0','').unique()
            data_df = data_df[data_df['Artikel'].astype(str).str.contains('|'.join(artikli_list))]
            
        else:
            data_df = data_df[data_df['Artikel'].isin(vsi_artikli_na_teh_strojih)]
    
    data_df['Stroj'].replace('', np.nan, inplace=True)
    data_df = data_df.dropna(subset=['Stroj'])
    
    data_df['Planirano_delovanje_strojne_ure'] = 0  # Initialize
    # Now we need to map Planirano_delovanje_strojne_ure
    data_df_agg = data_df.reset_index().set_index(['Stroj','Artikel' ,'Dnevni datum'])
    planirano_delovanje_dict = df_planirano_delovanje_groupby['Planirano_delovanje_strojne_ure'].to_dict()
    data_df_agg['Planirano_delovanje_strojne_ure'] = data_df_agg.index.map(planirano_delovanje_dict)
    data_df_agg = data_df_agg.reset_index()
    try:
        data_df_agg = update_planirano_delovanje_strojne_ure(data_df_agg, vrsta_strojev).set_index(['Stroj','Artikel' ,date_column])
    except:
        data_df_agg['Planirano_delovanje_strojne_ure'] = 24
        data_df_agg = data_df_agg.set_index(['Stroj','Artikel' ,date_column])
    data_df_agg['Planirano_delovanje_strojne_ure'] = pd.to_numeric(data_df_agg['Planirano_delovanje_strojne_ure'], errors='coerce').fillna(0).round(decimals=0)
    data_df_agg['Planirano_delovanje_strojne_ure'] = data_df_agg['Planirano_delovanje_strojne_ure'].apply(lambda x: min(24.0,x))
    data_df_agg['Planirano_delovanje_strojne_ure'] = data_df_agg['Planirano_delovanje_strojne_ure'].apply(lambda x: max(0,x))
    data_df_agg['Planirana_kolicina'] = data_df_agg['Kos/uro'] * data_df_agg['Planirano_delovanje_strojne_ure']
    data_df_agg['Planirana_kolicina'] = pd.to_numeric(data_df_agg['Planirana_kolicina'], errors='coerce').fillna(0)
    
    # breakpoint()
    # Step 2: Set the index for dictionary mapping
    # data_df_agg = data_df_agg.set_index(['Stroj', 'Artikel', date_column])
    
    # Step 3: Create dictionaries for each column we want to map
    planirano_delovanje_dict = data_df_agg['Planirano_delovanje_strojne_ure'].to_dict()
    planirana_kolicina_dict = data_df_agg['Planirana_kolicina'].to_dict()
    
    # Step 4: Map these values back to `data_df` using the index
    data_df['Planirano_delovanje_strojne_ure'] = data_df.set_index(['Stroj', 'Artikel', date_column]).index.map(planirano_delovanje_dict)
    data_df['Planirana_kolicina'] = data_df.set_index(['Stroj', 'Artikel', date_column]).index.map(planirana_kolicina_dict)
    
    # Step 5: Reset the index if needed and fill NaN values
    data_df = data_df.reset_index()
    data_df = data_df.fillna(0)
    data_df['Kolicina celice'] = pd.to_numeric(data_df['Kolicina celice'], errors='coerce').fillna(0)
    data_df['Izmet celice'] = pd.to_numeric(data_df['Izmet celice'], errors='coerce').fillna(0)
    data_df['Kos/uro'] = data_df['Kos/uro'].fillna(0).round(decimals=1)
    data_df['Artikel'].replace('', np.nan, inplace=True)
    data_df['Artikel'].replace('0', np.nan, inplace=True)
    data_df = data_df[~((data_df['Kolicina celice'] == 0) & (data_df['Izmet celice'] == 0) & (~data_df['Artikel'].isna()))]
    data_df = data_df.dropna(subset=['Artikel'])
    
    if radios_dtm == 'D':
        data_df[date_column_aux] = data_df[date_column].dt.weekday.apply(lambda x: dnevi_dict_full[x])
    elif radios_dtm == 'M':
        data_df[date_column_aux] = data_df[date_column].dt.month.apply(lambda x: meseci_dict[x])
    elif radios_dtm == 'T':
        data_df[date_column_aux] = data_df[date_column]
    
    data_dict_po_postajah[vrsta_strojev] = data_df.copy()
    
    stroj_artikel_pairs = [(row['Stroj'], row['Artikel']) for _, row in data_df.iterrows()]
    unique_stroj_artikel_pairs = list(set(stroj_artikel_pairs))
    unique_stroj_artikel_pairs.sort()
    artikli_list = (np.unique(data_df['Artikel'].values))

    data_df_izmene_tooltip = data_df.groupby(['Stroj', 'Artikel', date_column_aux, 'Izmena']).agg({
        'Kolicina celice': 'sum',
        'Izmet celice': 'sum'
        }).reset_index()
    
    data_df = data_df.groupby(['Stroj', 'Artikel', date_column_aux]).agg({
        'Kolicina celice': 'sum',
        'Izmet celice': 'sum',
        'Plan': 'first',
        'Kos/uro': 'first',
        'Planirano_delovanje_strojne_ure': 'first',
        'Planirana_kolicina': 'first',
    }).reset_index().fillna(0)
    
    data_planirane_kolicine_dict[vrsta_strojev] = data_df.copy()
    data_dict_po_izmenah_tooltip_dict[vrsta_strojev] = data_df_izmene_tooltip.copy()
    data_dict_po_izmenah_zaposleni_tooltip_dict[vrsta_strojev] = fetch_realizacija_proizvodnje_zaposleni(start_date_object, end_date_object, list_of_machines)
    
    data_df = pivot_and_merge_with_plan(data_df, date_column_aux, radios_dtm)

    
    data_df = data_df.rename_axis(['Stroj', 'Artikel','Plan'], axis='index')
    extra_columns = [('Št. izm','Št. izm','Št. izm'),('Zaloga artiklov','Zaloga artiklov','Zaloga artiklov'),('Plan','Plan','Plan')]
    # breakpoint()
    extra_columns_singular = [x[0] for x in extra_columns]            
    data_df.columns = [str(col[1])+' '+ '✔️' if str(col[0])[:3]=='Kol' else '❌' if not str(col[0]) in extra_columns_singular else col[0] for col in data_df.columns]
    data_df.columns = dedup_columns_space(data_df)
    data_df.reset_index(inplace=True)
    columns_order = ['Stroj','Artikel']+extra_columns_singular
    data_df['Št. izm'] = None
    data_df['Zaloga artiklov'] = None
    data_df = data_df[columns_order+[x for x in data_df.columns if not x in columns_order]]
    
    if identifier == '_bosch' or machines_to_include:
        pass
    else:
        if vrsta_strojev in ['Litje', 'Peskanje','Obdelava','Pranje','Preizkus tesnosti'] + variables[f'vrste_strojev_extra{identifier}']:
            machines_to_add = [m for m in list_of_machines if m not in data_df['Stroj'].unique()]
            new_machines_df = pd.DataFrame({'Stroj': machines_to_add})
            columns_with_strings = ['Artikel', 'Št. izm']
            for col in columns_with_strings:
                data_df[col] = data_df[col].astype(str)
            for col in data_df.columns:
                if col in columns_with_strings:
                    new_machines_df[col] = '/'
                elif col != 'Stroj':
                    new_machines_df[col] = 0
            try:
                data_df = pd.concat([data_df, new_machines_df]).reset_index(drop=True).fillna(0)
            except:
                pass
        else:
            data_df = data_df.reset_index(drop=True).fillna(0)
    
    if not isinstance(artikli_list, type(None)):
        if not vrsta_strojev == 'Pranje':
            vsi_artikli = vsi_artikli + list(artikli_list)
    
    try:
        fetched_zaloga_dict = fetch_zaloga_bulk(artikli_list, vrsta_strojev, engine)
        data_df['Zaloga artiklov'] = data_df['Artikel'].map(lambda x: fetched_zaloga_dict.get(x, 0))
    except Exception as e:
        print(f"Error fetching data: {e}")
        pass
    
    if not isinstance(artikli_list, type(None)):
        if not vrsta_strojev == 'Pranje':
            vsi_artikli = vsi_artikli + list(artikli_list)
    
    data_df['Zaloga artiklov'] = pd.to_numeric(data_df['Zaloga artiklov'], errors='coerce').fillna(0)
    data_df = assign_plan_teden_and_st_izm(data_df, stroj_artikel_pairs, week, engine)

    if tagname_tim == 'bmw':
        data_df = data_df.sort_values(['Artikel'])
    else:
        data_df['Stroj'] = pd.Categorical(data_df['Stroj'], categories=list_of_machines, ordered=True)
        data_df = data_df.sort_values(['Stroj', 'Artikel'])

    return data_df, data_dict, data_kontrolni_list_dict, data_zadnji_nalog_dict, data_dict_sum, data_dict_po_izmenah, data_dict_po_postajah, data_dict_po_izmenah_tooltip_dict, data_dict_po_izmenah_zaposleni_tooltip_dict, data_planirane_kolicine_dict, vsi_artikli, stroj_artikel_pairs, list_of_machines, date_column, date_column_aux

