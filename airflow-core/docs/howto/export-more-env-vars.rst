 .. Licensed to the Apache Software Foundation (ASF) under one
    or more contributor license agreements.  See the NOTICE file
    distributed with this work for additional information
    regarding copyright ownership.  The ASF licenses this file
    to you under the Apache License, Version 2.0 (the
    "License"); you may not use this file except in compliance
    with the License.  You may obtain a copy of the License at

 ..   http://www.apache.org/licenses/LICENSE-2.0

 .. Unless required by applicable law or agreed to in writing,
    software distributed under the License is distributed on an
    "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
    KIND, either express or implied.  See the License for the
    specific language governing permissions and limitations
    under the License.


.. _export_dynamic_environment_variables:

Export dynamic environment variables available for operators to use
===================================================================


The key value pairs returned in ``get_airflow_context_vars`` defined in
``airflow_local_settings.py`` are injected to default Airflow context environment variables,
which are available as environment variables when running tasks. Note, both key and
value are must be string.

``dag_id``, ``task_id``, ``execution_date``, ``dag_run_id``,
``dag_owner``, ``dag_email`` are reserved keys.

For example, in your ``airflow_local_settings.py`` file:

.. code-block:: python

  def get_airflow_context_vars(context) -> dict[str, str]:
      """
      :param context: The context for the task_instance of interest.
      """
      # more env vars
      return {"airflow_cluster": "main"}


See :ref:`Configuring local settings <set-config:configuring-local-settings>` for details on how to
configure local settings.
