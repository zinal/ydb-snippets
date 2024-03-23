package ru.zinal.lockrecord;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.Properties;
import tech.ydb.auth.iam.CloudAuthHelper;
import tech.ydb.core.auth.StaticCredentials;
import tech.ydb.core.grpc.GrpcTransport;
import tech.ydb.core.grpc.GrpcTransportBuilder;
import tech.ydb.table.SessionRetryContext;
import tech.ydb.table.TableClient;

/**
 * The helper class which creates the YDB connection from the set of properties.
 *
 * @author mzinal
 */
public class YdbConnector implements AutoCloseable {

    private static final org.slf4j.Logger LOG = org.slf4j.LoggerFactory.getLogger(YdbConnector.class);

    private final GrpcTransport transport;
    private final TableClient tableClient;
    private final SessionRetryContext retryCtx;
    private final String database;
    private final YdbConfig config;

    public YdbConnector(GrpcTransport transport, TableClient tableClient,
            SessionRetryContext retryCtx, String database) {
        this.transport = transport;
        this.tableClient = tableClient;
        this.retryCtx = retryCtx;
        this.database = database;
        this.config = new YdbConfig();
    }

    public YdbConnector(YdbConfig config) {
        GrpcTransportBuilder builder = GrpcTransport
                .forConnectionString(config.getConnectionString());
        switch (config.getAuthMode()) {
            case ENV:
                builder = builder.withAuthProvider(
                        CloudAuthHelper.getAuthProviderFromEnviron());
                break;
            case STATIC:
                builder = builder.withAuthProvider(
                        new StaticCredentials(config.getStaticLogin(), config.getStaticPassword()));
                break;
            case METADATA:
                builder = builder.withAuthProvider(
                        CloudAuthHelper.getMetadataAuthProvider());
                break;
            case SAKEY:
                builder = builder.withAuthProvider(
                        CloudAuthHelper.getServiceAccountFileAuthProvider(config.getSaKeyFile()));
                break;
            case NONE:
                break;
        }
        String tlsCertFile = config.getTlsCertificateFile();
        if (tlsCertFile != null && tlsCertFile.length() > 0) {
            byte[] cert;
            try {
                cert = Files.readAllBytes(Paths.get(tlsCertFile));
            } catch (IOException ix) {
                throw new RuntimeException("Failed to read file " + tlsCertFile, ix);
            }
            builder.withSecureConnection(cert);
        }

        GrpcTransport tempTransport = builder.build();
        this.database = tempTransport.getDatabase();
        try {
            this.tableClient = TableClient.newClient(tempTransport)
                    .sessionPoolSize(0, config.getPoolSize())
                    .build();
            this.retryCtx = SessionRetryContext
                    .create(tableClient)
                    .idempotent(true)
                    .build();
            this.transport = tempTransport;
            tempTransport = null; // to avoid closing below
        } finally {
            if (tempTransport != null) {
                tempTransport.close();
            }
        }
        this.config = config;
    }

    public YdbConnector(Properties props) {
        this(new YdbConfig(props));
    }

    public YdbConnector(Properties props, String prefix) {
        this(new YdbConfig(props, prefix));
    }

    public YdbConfig getConfig() {
        return config;
    }

    public TableClient getTableClient() {
        return tableClient;
    }

    public SessionRetryContext getRetryCtx() {
        return retryCtx;
    }

    public String getDatabase() {
        return database;
    }

    @Override
    public void close() {
        if (tableClient != null) {
            try {
                tableClient.close();
            } catch (Exception ex) {
                LOG.warn("TableClient closing threw an exception", ex);
            }
        }
        if (transport != null) {
            try {
                transport.close();
            } catch (Exception ex) {
                LOG.warn("GrpcTransport closing threw an exception", ex);
            }
        }
    }

}
