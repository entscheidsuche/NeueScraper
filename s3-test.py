import boto3
import os

s3 = boto3.resource('s3')
for bucket in s3.buckets.all():
	print(bucket.name)

client= boto3.client('s3')

"""for file in os.listdir():
	if '.py'in file:
		upload_file_bucket = 'entscheidsuche.ch'
		upload_file_key = 'test/' + str(file)
		client.upload_file(file, upload_file_bucket, upload_file_key)
"""

upload_file_bucket = 'entscheidsuche.ch'
upload_file_key = 'test/test.txt'
upload_file_content = 'This is a test.'
upload_file_ACL = 'public-read'

client.put_object(Body=upload_file_content, Bucket=upload_file_bucket, Key=upload_file_key, ACL=upload_file_ACL)
