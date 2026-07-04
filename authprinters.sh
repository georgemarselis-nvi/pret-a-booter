#!/bin/sh

# Authenticate all mapped printers

#get the list of mapped printers and copy to temp file
#all network printer names in caps - filter non-printer text
/usr/bin/lpstat -p | awk '{print $2}' > /tmp/authPrinterList.txt

#read through mapped printer list and apply authentication
while read printerName
do
    /usr/sbin/lpadmin -p $printerName -o auth-info-required=negotiate
	lpr -P $printerName authprinters.sh
done < /tmp/authPrinterList.txt

exit 0
