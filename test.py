import sys
import traceback
import re

filenamechars=re.compile("(?u)[^-\\w.]")

try:
	test="jakhah//oue.dsd"
	print(filenamechars.sub("",test))
except:
	exc_type, exc_value, exc_traceback = sys.exc_info()
	print("Fehler: "+repr(traceback.format_exception(exc_type, exc_value, exc_traceback)))
