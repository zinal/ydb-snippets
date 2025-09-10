```bash
sudo apt-get install openjdk-21-jdk maven
mvn clean package
mvn exec:java -Dexec.args=connect.xml
```