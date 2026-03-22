package tech.ydb.samples.strangeparam;

import java.util.Arrays;
import tech.ydb.common.transaction.TxMode;
import tech.ydb.table.query.Params;
import tech.ydb.table.values.PrimitiveType;
import tech.ydb.table.values.PrimitiveValue;
import tech.ydb.table.values.StructType;

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
                    -> session.createQuery(QUERY, TxMode.NONE, params).execute()).join();

            System.out.println("Success: " + result.isSuccess());
            System.out.println("Status : " + result.getStatus());
            if (!result.isSuccess()) {
                System.out.println("Issues : " + Arrays.toString(result.getStatus().getIssues()));
            }
        }
    }

    private static Params buildMismatchedParams() {
        StructType level3Actual = StructType.of(
                "q", PrimitiveType.Int32,
                "p", PrimitiveType.Uint32
        );
        StructType level2Actual = StructType.of(
                "a", PrimitiveType.Int32,
                "b", PrimitiveType.Int32,
                "c", level3Actual
        );
        StructType rootActual = StructType.of(
                "x", PrimitiveType.Int32,
                "y", PrimitiveType.Uint32.makeOptional(),
                "z", level2Actual
        );

        return Params.of("$items", rootActual.newValue(
                "x", PrimitiveValue.newInt32(1),
                "y", PrimitiveValue.newUint32(2).makeOptional(),
                "z", level2Actual.newValue(
                        "a", PrimitiveValue.newInt32(1),
                        "b", PrimitiveValue.newInt32(2),
                        "c", level3Actual.newValue(
                                "q", PrimitiveValue.newInt32(1),
                                "p", PrimitiveValue.newUint32(2)
                        )
                )
        ));
    }
}
