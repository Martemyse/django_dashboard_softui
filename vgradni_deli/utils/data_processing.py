# utils/data_processing.py
import pandas as pd

def process_machine_data(data_df, radios_dtm):
    df = pd.DataFrame(raw_data)
    
    # Add calculated fields (Plan, Realizacija, etc.)
    df['Plan'] = df['Kolicina celice'] * 2  # Example calculation
    df['Realizacija'] = (df['Kolicina celice'] / df['Plan']) * 100

    # Pivot data for AG Grid (example)
    if radios_dtm == 'D':
        pivoted = df.pivot(index='Stroj', columns='Dnevni datum', values='Kolicina celice')
    else:
        pivoted = df.groupby('Stroj')['Kolicina celice'].sum()

    return pivoted.reset_index()
