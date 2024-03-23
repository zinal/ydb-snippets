package ru.zinal.lockrecord;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.Properties;

/**
 *
 * @author mzinal
 */
public class YdbConfig {

    private String connectionString;
    private YdbAuthMode authMode = YdbAuthMode.NONE;
    private String saKeyFile;
    private String staticLogin;
    private String staticPassword;
    private String tlsCertificateFile;
    private int poolSize = 2 * (1 + Runtime.getRuntime().availableProcessors());
    private final String prefix;
    private final Properties properties = new Properties();

    public YdbConfig() {
        this.prefix = "ydb.";
    }

    public YdbConfig(Properties props) {
        this(props, null);
    }

    public YdbConfig(Properties props, String prefix) {
        if (prefix==null) {
            prefix = "ydb.";
        }
        this.prefix = prefix;
        this.connectionString = props.getProperty(prefix + "url");
        this.authMode = YdbAuthMode.valueOf(props.getProperty(prefix + "auth.mode", "NONE"));
        this.saKeyFile = props.getProperty(prefix + "auth.sakey");
        this.staticLogin = props.getProperty(prefix + "auth.username");
        this.staticPassword = props.getProperty(prefix + "auth.password");
        this.tlsCertificateFile = props.getProperty(prefix + "cafile");
        String spool = props.getProperty(prefix + "poolSize");
        if (spool!=null && spool.length() > 0) {
            poolSize = Integer.parseInt(spool);
        }
        this.properties.putAll(props);
    }

    public static YdbConfig fromFile(String fname) {
        return fromFile(fname, null);
    }

    public static YdbConfig fromFile(String fname, String prefix) {
        byte[] data;
        try {
            data = Files.readAllBytes(Paths.get(fname));
        } catch(IOException ix) {
            throw new RuntimeException("Failed to read file " + fname, ix);
        }
        Properties props = new Properties();
        try {
            props.loadFromXML(new ByteArrayInputStream(data));
        } catch(IOException ix) {
            throw new RuntimeException("Failed to parse properties file " + fname, ix);
        }
        return new YdbConfig(props, prefix);
    }

    public String getPrefix() {
        return prefix;
    }

    public String getConnectionString() {
        return connectionString;
    }

    public void setConnectionString(String connectionString) {
        this.connectionString = connectionString;
    }

    public YdbAuthMode getAuthMode() {
        return authMode;
    }

    public void setAuthMode(YdbAuthMode authMode) {
        if (authMode==null) {
            authMode = YdbAuthMode.NONE;
        }
        this.authMode = authMode;
    }

    public String getSaKeyFile() {
        return saKeyFile;
    }

    public void setSaKeyFile(String saKeyFile) {
        this.saKeyFile = saKeyFile;
    }

    public String getStaticLogin() {
        return staticLogin;
    }

    public void setStaticLogin(String staticLogin) {
        this.staticLogin = staticLogin;
    }

    public String getStaticPassword() {
        return staticPassword;
    }

    public void setStaticPassword(String staticPassword) {
        this.staticPassword = staticPassword;
    }

    public String getTlsCertificateFile() {
        return tlsCertificateFile;
    }

    public void setTlsCertificateFile(String tlsCertificateFile) {
        this.tlsCertificateFile = tlsCertificateFile;
    }

    public int getPoolSize() {
        return poolSize;
    }

    public void setPoolSize(int poolSize) {
        if (poolSize <=0) {
            poolSize = 2 * (1 + Runtime.getRuntime().availableProcessors());
        }
        this.poolSize = poolSize;
    }

    public Properties getProperties() {
        return properties;
    }

    public static enum YdbAuthMode {

        NONE,
        ENV,
        STATIC,
        METADATA,
        SAKEY

    }
}
