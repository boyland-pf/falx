import os

myDIR = "/Users/peter/Documents/UCSB/falx/falx/falx/petereval"

triesToCompleteDict = {}

#for each file in the correct folder (petereval), read each one

for filename in os.listdir(myDIR):
	if filename.endswith(".log"):
		with open(os.path.join(myDIR,filename), 'r') as f:
			for line in f.readlines():
				if line.startswith("# candidates before getting the correct solution: "):
					triesToCompleteDict[filename] = int(line.split(":")[-1].strip()) + 1


for limit in {1, 3, 5, 10}:
	count = 0
	for k in triesToCompleteDict.keys():
		if triesToCompleteDict[k] < limit:
			count += 1
	print("Number in top " + str(limit) + " = " + str(count))