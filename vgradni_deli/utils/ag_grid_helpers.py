# utils/ag_grid_helpers.py
def generate_ag_grid_json(data_frame):
    columns = [{'headerName': col, 'field': col, 'editable': False} for col in data_frame.columns]
    rows = data_frame.to_dict('records')
    return {'columns': columns, 'rows': rows}
