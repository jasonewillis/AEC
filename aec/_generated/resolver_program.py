RESOLVER_PROGRAM = {'decision_schema_version': '3.0.0',
 'outcomes': {'evidence_complete': {'allowed': True,
                                    'gate': 'Ready',
                                    'reason_code': 'ACCEPTANCE_EVIDENCE_COMPLETE'},
              'evidence_incomplete': {'allowed': True,
                                      'gate': 'Evidence needed',
                                      'reason_code': None},
              'skill_unavailable': {'allowed': False,
                                    'anti_example': 'Another available procedure is '
                                                    'silently substituted.',
                                    'finished': ['The required procedure is available '
                                                 'at its pinned revision.'],
                                    'gate': 'Blocked',
                                    'good': ['The required procedure is available '
                                             'before it is recommended.'],
                                    'rationale_summary': 'The required procedure is '
                                                         'unavailable for the '
                                                         'requested phase.',
                                    'reason_code': 'SKILL_UNAVAILABLE',
                                    'required_evidence': ['procedure-availability']}},
 'schema_version': '1.0.0'}
