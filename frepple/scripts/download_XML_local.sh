
SERVER="172.18.0.3:8069"  # Add here your IP & port from your local Docker container
DB="minditpfr_test_v13"   # Add here the db name from your local
COMPANY="M-Industrie%20France"
PASSWORD="frepple"
XSD_FILE="xml/frepple_6.11.0.xsd"
DATETIME=$(date "+%Y-%m-%d_%H-%M-%S")
OUTPUT_FILE_XML="frepple-v13-$DATETIME.xml"
OUTPUT_FILE_CHK="frepple-v13-$DATETIME.xmllint.txt"
URL="http://$SERVER/frepple/xml/?company=$COMPANY&database=$DB&language=en_US"


echo "downloading XML from $SERVER, DB $DB, company $COMPANY"
echo "the url is: $URL"
echo "and saving to $OUTPUT_FILE_XML"

wget --user frepple --password $PASSWORD --output-document $OUTPUT_FILE_XML $URL
DATETIME_END=$(date "+%Y-%m-%d_%H-%M-%S")
echo "started at $DATETIME and ended at $DATETIME_END"


echo "checking XML against schema $XSD_FILE and saving to $OUTPUT_FILE_CHK"
echo "checking XML $OUTPUT_FILE_XML against schema $XSD_FILE:" >$OUTPUT_FILE_CHK
xmllint --schema $XSD_FILE $OUTPUT_FILE_XML 1>/dev/null 2>$OUTPUT_FILE_CHK
echo "just to repeat in case you missed it or xmllint's out put was too long: download started at $DATETIME and ended at $DATETIME_END"
