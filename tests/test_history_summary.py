import ast
from pathlib import Path
from types import SimpleNamespace
import datetime as dt
import unittest
from sqlalchemy import create_engine, MetaData, Table, Column, DateTime, Float, Index, event
from sqlalchemy.orm import Session
from history_summary import read_history_summary


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        metadata = MetaData()
        self.table = Table('portfolio_history', metadata, Column('date', DateTime), Column('total_value', Float))
        Index('ix_portfolio_history_date', self.table.c.date)
        metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.now = dt.datetime(2026, 8, 30, 15, 45)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def add(self, hours, value):
        self.session.execute(self.table.insert().values(date=self.now-dt.timedelta(hours=hours), total_value=value))

    def test_endpoint_requires_login_and_returns_compact_payload(self):
        from flask import Flask, jsonify
        from flask_login import LoginManager, UserMixin, login_required
        app = Flask(__name__)
        app.secret_key = 'test-only'
        manager = LoginManager(app)
        user = UserMixin()
        user.id = 'test'
        manager.user_loader(lambda user_id: user)
        definition = next(node for node in ast.parse(Path('app.py').read_text()).body
                          if isinstance(node, ast.FunctionDef) and node.name == 'get_history_summary')
        namespace = dict(app=app, jsonify=jsonify, login_required=login_required,
                         read_history_summary=read_history_summary,
                         db=SimpleNamespace(session=self.session),
                         PortfolioHistory=SimpleNamespace(__table__=self.table),
                         logger=app.logger)
        exec(compile(ast.Module(body=[definition], type_ignores=[]), 'app.py', 'exec'), namespace)
        client = app.test_client()
        self.assertEqual(client.get('/history/summary').status_code, 401)
        with client.session_transaction() as session:
            session['_user_id'] = 'test'
            session['_fresh'] = True
        response = client.get('/history/summary')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['data']['comparisons']), 3)
        self.assertLess(len(response.data), 500)

    def test_nearest_samples_preserve_time_and_only_bounded_queries(self):
        for hours, value in [(25, 100), (23.5, 110), (168, 200), (720, 300)]: self.add(hours, value)
        statements = []
        event.listen(self.engine, 'before_cursor_execute', lambda c, cur, sql, params, context, many: statements.append(sql))
        data = read_history_summary(self.session, self.table, self.now)
        self.assertEqual(data['comparisons']['change24h']['total_value'], 110)
        self.assertEqual(data['comparisons']['change7d']['total_value'], 200)
        self.assertEqual(data['comparisons']['change30d']['total_value'], 300)
        self.assertIn('T16:15:00', data['comparisons']['change24h']['datetime'])
        self.assertEqual(len(statements), 6)
        self.assertTrue(all('LIMIT' in sql and 'ORDER BY' in sql for sql in statements))

    def test_empty_and_stale_history_are_unavailable(self):
        self.add(5000, 100)
        self.assertTrue(all(v is None for v in read_history_summary(self.session,self.table,self.now)['comparisons'].values()))

    def test_zero_baseline_not_replaced_by_more_distant_sample(self):
        self.add(24, 0)
        self.add(25, 100)
        self.assertIsNone(read_history_summary(self.session,self.table,self.now)['comparisons']['change24h'])

    def test_tie_prefers_earlier_snapshot(self):
        self.add(25, 100)
        self.add(23, 200)
        self.assertEqual(read_history_summary(self.session,self.table,self.now)['comparisons']['change24h']['total_value'],100)

    def test_single_valid_sample_suffices(self):
        self.add(24, 100)
        data=read_history_summary(self.session,self.table,self.now)['comparisons']
        self.assertEqual(data['change24h']['total_value'],100)
        self.assertIsNone(data['change7d'])

if __name__ == '__main__': unittest.main()
