
```bash
mvn clean package
export YDB_URL='jdbc:ydb:grpcs://<host>:2135/Root/<testdb>?secureConnectionCertificate=file:~/<myca>.cer'
export YDB_USER=root
export YDB_PASSWORD='...'
mvn exec:java
```
