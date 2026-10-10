"""F4.1 regression tests for embedded DB2 SQL and CICS commands."""

import unittest

from rezonator.ast_graph_builder import CobolASTGraphBuilder
from rezonator.graph_field import GraphField


ENTERPRISE_SOURCE = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. F4-ENTERPRISE.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-ACCOUNT-ID PIC X(10).
       01 WS-BALANCE PIC 9(7)V99.
       PROCEDURE DIVISION.
       MAIN.
           EXEC SQL
               SELECT A.BALANCE
                 INTO :WS-BALANCE
                 FROM BANK.ACCOUNTS A
                WHERE A.ACCOUNT_ID = :WS-ACCOUNT-ID
           END-EXEC.
           EXEC CICS LINK PROGRAM('RISK-CHECK') END-EXEC.
           EXEC CICS SEND MAP('BANKMAP') MAPSET('BANKSET') END-EXEC.
           EXEC CICS RECEIVE MAP('BANKMAP') MAPSET('BANKSET') END-EXEC.
           EXEC CICS SYNCPOINT END-EXEC.
           EXEC CICS XCTL PROGRAM('NEXT-SCREEN') END-EXEC.
           STOP RUN.
"""


class TestF4EnterpriseStatements(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = CobolASTGraphBuilder().build_from_source(ENTERPRISE_SOURCE)
        cls.nodes = {node["id"]: node for node in cls.data["nodes"]}

    def test_sql_is_a_typed_graph_node_with_host_variable_flow(self):
        sql_nodes = [node for node in self.nodes.values() if node.get("node_type") == "db_access"]
        self.assertEqual(len(sql_nodes), 1)

        sql = sql_nodes[0]
        self.assertEqual(sql["sql_operation"], "SELECT")
        self.assertEqual(sql["tables"], ["BANK.ACCOUNTS"])
        self.assertEqual(sql["reads"], ["WS-ACCOUNT-ID"])
        self.assertEqual(sql["writes"], ["WS-BALANCE"])

        table_id = "db_table:BANK.ACCOUNTS"
        self.assertIn(table_id, self.nodes)
        self.assertIn(
            (table_id, sql["id"], "dfg_db_read"),
            {(e["source"], e["target"], e["edge_type"]) for e in self.data["edges"]},
        )

    def test_cics_commands_create_external_transfer_edges(self):
        cics_nodes = [node for node in self.nodes.values() if node.get("node_type") == "external"]
        self.assertEqual(len(cics_nodes), 5)
        self.assertEqual(
            {node["cics_command"] for node in cics_nodes},
            {"LINK", "SEND MAP", "RECEIVE MAP", "SYNCPOINT", "XCTL"},
        )

        edges = {(e["source"], e["target"], e["edge_type"]) for e in self.data["edges"]}
        for node in cics_nodes:
            resource_id = f"cics_resource:{node['resource_kind']}:{node['resource_name']}"
            self.assertIn(resource_id, self.nodes)
            self.assertIn((node["id"], resource_id, "cfg_external"), edges)

    def test_resources_are_connected_to_the_mathematical_graph(self):
        field = GraphField(self.data, symmetrize=True, include_variables=True)
        self.assertIn("db_table:BANK.ACCOUNTS", field.node_id_to_idx)
        self.assertIn("cics_resource:PROGRAM:RISK-CHECK", field.node_id_to_idx)
        self.assertIn("cics_resource:MAP:BANKMAP", field.node_id_to_idx)
        self.assertIn("cics_resource:TRANSACTION:SYNCPOINT", field.node_id_to_idx)
        self.assertIn("cics_resource:PROGRAM:NEXT-SCREEN", field.node_id_to_idx)
        self.assertNotIn("db_table:BANK.ACCOUNTS", field.isolated_nodes)
        self.assertNotIn("cics_resource:PROGRAM:RISK-CHECK", field.isolated_nodes)
        self.assertNotIn("cics_resource:MAP:BANKMAP", field.isolated_nodes)
        self.assertNotIn("cics_resource:TRANSACTION:SYNCPOINT", field.isolated_nodes)
        self.assertNotIn("cics_resource:PROGRAM:NEXT-SCREEN", field.isolated_nodes)


if __name__ == "__main__":
    unittest.main()
