package tech.ydb.samples.strangeparam;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.Properties;
import tech.ydb.auth.iam.CloudAuthHelper;
import tech.ydb.core.auth.StaticCredentials;
import tech.ydb.core.grpc.GrpcTransport;
import tech.ydb.core.grpc.GrpcTransportBuilder;
import tech.ydb.query.QueryClient;
import tech.ydb.query.tools.SessionRetryContext;

public final class YdbConnector implements AutoCloseable {
    private final GrpcTransport transport;
    private final QueryClient queryClient;
    private final SessionRetryContext retryCtx;

    public YdbConnector(Config config) {
        GrpcTransportBuilder builder = GrpcTransport.forConnectionString(config.connectionString);
        switch (config.authMode) {
            case ENV:
                builder = builder.withAuthProvider(CloudAuthHelper.getAuthProviderFromEnviron());
                break;
            case STATIC:
                builder = builder.withAuthProvider(
                        new StaticCredentials(config.staticLogin, config.staticPassword));
                break;
            case METADATA:
                builder = builder.withAuthProvider(CloudAuthHelper.getMetadataAuthProvider());
                break;
            case SAKEY:
                builder = builder.withAuthProvider(
                        CloudAuthHelper.getServiceAccountFileAuthProvider(config.saKeyFile));
                break;
            case NONE:
                break;
        }
        if (config.tlsCertificateFile != null && !config.tlsCertificateFile.isBlank()) {
            try {
                builder.withSecureConnection(Files.readAllBytes(Paths.get(config.tlsCertificateFile)));
            } catch (IOException ex) {
                throw new IllegalArgumentException("Failed to read TLS CA file: " + config.tlsCertificateFile, ex);
            }
        }

        this.transport = builder.build();
        this.queryClient = QueryClient.newClient(transport)
                .sessionPoolMinSize(1)
                .sessionPoolMaxSize(config.poolSize)
                .build();
        this.retryCtx = SessionRetryContext.create(queryClient)
                .idempotent(true)
                .build();
    }

    public SessionRetryContext getRetryCtx() {
        return retryCtx;
    }

    @Override
    public void close() {
        queryClient.close();
        transport.close();
    }

    public static final class Config {
        private String connectionString;
        private AuthMode authMode = AuthMode.NONE;
        private String saKeyFile;
        private String staticLogin;
        private String staticPassword;
        private String tlsCertificateFile;
        private int poolSize = 8;

        public static Config fromFile(String fileName) {
            try {
                byte[] data = Files.readAllBytes(Paths.get(fileName));
                Properties props = new Properties();
                props.loadFromXML(new ByteArrayInputStream(data));
                return fromProperties(props);
            } catch (IOException ex) {
                throw new IllegalArgumentException("Failed to read config file: " + fileName, ex);
            }
        }

        public static Config fromProperties(Properties props) {
            Config cfg = new Config();
            cfg.connectionString = props.getProperty("ydb.url");
            cfg.authMode = AuthMode.valueOf(props.getProperty("ydb.auth.mode", "NONE"));
            cfg.saKeyFile = props.getProperty("ydb.auth.sakey");
            cfg.staticLogin = props.getProperty("ydb.auth.username");
            cfg.staticPassword = props.getProperty("ydb.auth.password");
            cfg.tlsCertificateFile = props.getProperty("ydb.cafile");
            String pool = props.getProperty("ydb.poolSize");
            if (pool != null && !pool.isBlank()) {
                cfg.poolSize = Integer.parseInt(pool);
            }
            if (cfg.connectionString == null || cfg.connectionString.isBlank()) {
                throw new IllegalArgumentException("Missing required property: ydb.url");
            }
            return cfg;
        }
    }

    public enum AuthMode {
        NONE,
        ENV,
        STATIC,
        METADATA,
        SAKEY
    }
}
