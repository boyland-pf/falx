import json
import pandas as pd

def infer_dtype(values):
	return pd.api.types.infer_dtype(values, skipna=True)

def filter_table(table, pred):
	#TODO: implement filter function
	print("# [unimplemented] filter table by pred {}".format(pred))
	return table

def clean_column_dtype(column_values):
	dtype = pd.api.types.infer_dtype(column_values, skipna=True)

	if dtype != "string":
		return dtype, column_values

	def try_infer_string_type(values):
		"""try to infer datatype from values """
		dtype = pd.api.types.infer_dtype(values, skipna=True)
		ty_check_functions = [
			lambda l: pd.to_numeric(l),
			lambda l: pd.to_datetime(l, infer_datetime_format=True)
		]
		for ty_func in ty_check_functions:
			try:
				values = ty_func(values)
				dtype = pd.api.types.infer_dtype(values, skipna=True)
			except:
				pass
			if dtype != "stirng":
				break
		return dtype, values

	def to_time(l):
		return l[0] * 60 + l[1]

	convert_functions = {
		"id": (lambda l: True, lambda l: l),
		"percentage": (lambda l: all(["%" in x for x in l]), 
					   lambda l: [x.replace("%", "").replace(" ", "") if x.strip() not in [""] else "" for x in l]),
		"currency": (lambda l: True, lambda l: [x.replace("$", "").replace(",", "") for x in l]),
		"cleaning_missing_number": (lambda l: True, lambda l: [x if x.strip() not in [""] else "" for x in l]),
		"cleaning_time_value": (lambda l: True, lambda l: [to_time([int(y) for y in x.split(":")]) for x in l]),
	}

	for key in convert_functions:
		if convert_functions[key][0](column_values):
			try:
				converted_values = convert_functions[key][1](column_values)
			except:
				continue
			dtype, values = try_infer_string_type(converted_values)
		if dtype != "string": 
			if key == "percentage":
				values = values / 100.
			break
	return dtype, values


def load_and_clean_table(input_data):
	# infer type of each column and then update column value
	for col in input_data:
		dtype, new_col_values = clean_column_dtype(input_data[col])
		input_data[col] = new_col_values
	return input_data