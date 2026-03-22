package tech.ydb.samples.strangeparam;

import tech.ydb.common.transaction.TxMode;
import tech.ydb.table.query.Params;
import tech.ydb.table.values.PrimitiveValue;
import tech.ydb.table.values.StructValue;

public class Main {

    private static final String QUERY = """
            DECLARE $items AS Struct<x:Int32, y:Uint32, z:Struct<a:Int32, b:Int32, c:Struct<q:Int32, p:Int32>>>;
            SELECT * FROM AS_TABLE([ $items ]);
            """;

    public static void main(String[] args) {
        String configFile = args.length > 0 ? args[0] : "example1.xml";

        try (YdbConnector connector = new YdbConnector(YdbConnector.Config.fromFile(configFile))) {
            Params params = buildMismatchedParams();

            var result = connector.getRetryCtx().supplyResult(session
                    -> session.createQuery(QUERY, TxMode.SERIALIZABLE_RW, params).execute()).join();

            System.out.println("Success: " + result.isSuccess());
            System.out.println("Status : " + result.getStatus());
        }
    }

    private static Params buildMismatchedParams() {
        return Params.of("$items",
                StructValue.of(
                        "x", PrimitiveValue.newInt32(1),
                        "y", PrimitiveValue.newUint32(2).makeOptional(),
                        "z", StructValue.of(
                                "a", PrimitiveValue.newInt32(1),
                                "b", PrimitiveValue.newInt32(2),
                                "c", StructValue.of(
                                        "q", PrimitiveValue.newInt32(1),
                                        "p", PrimitiveValue.newUint32(1)
                                )
                        ))
        );
    }
}
