# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""Objects relating to sourcing connections from Google Cloud Secrets Manager."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from google.auth.exceptions import DefaultCredentialsError

from airflow.exceptions import AirflowException
from airflow.providers.google.cloud._internal_client.secret_manager_client import _SecretManagerClient
from airflow.providers.google.cloud.utils.credentials_provider import (
    _get_target_principal_and_delegates,
    get_credentials_and_project_id,
)
from airflow.providers.google.common.hooks.base_google import PROVIDE_PROJECT_ID
from airflow.secrets import BaseSecretsBackend
from airflow.utils.log.logging_mixin import LoggingMixin

log = logging.getLogger(__name__)

SECRET_ID_PATTERN = r"^[a-zA-Z0-9-_]*$"


class CloudSecretManagerBackend(BaseSecretsBackend, LoggingMixin):
    """
    Retrieves Connection object from Google Cloud Secrets Manager.

    Configurable via ``airflow.cfg`` as follows:

    .. code-block:: ini

        [secrets]
        backend = airflow.providers.google.cloud.secrets.secret_manager.CloudSecretManagerBackend
        backend_kwargs = {"connections_prefix": "airflow-connections", "sep": "-"}

    For example, if the Secrets Manager secret id is ``airflow-connections-smtp_default``, this would be
    accessible if you provide ``{"connections_prefix": "airflow-connections", "sep": "-"}`` and request
    conn_id ``smtp_default``.

    If the Secrets Manager secret id is ``airflow-variables-hello``, this would be
    accessible if you provide ``{"variables_prefix": "airflow-variables", "sep": "-"}`` and request
    Variable Key ``hello``.

    The full secret id should follow the pattern "[a-zA-Z0-9-_]".

    :param connections_prefix: Specifies the prefix of the secret to read to get Connections.
        If set to None (null), requests for connections will not be sent to GCP Secrets Manager
    :param variables_prefix: Specifies the prefix of the secret to read to get Variables.
        If set to None (null), requests for variables will not be sent to GCP Secrets Manager
    :param config_prefix: Specifies the prefix of the secret to read to get Airflow Configurations
        containing secrets.
        If set to None (null), requests for configurations will not be sent to GCP Secrets Manager
    :param gcp_key_path: Path to Google Cloud Service Account key file (JSON). Mutually exclusive with
        gcp_keyfile_dict. use default credentials in the current environment if not provided.
    :param gcp_keyfile_dict: Dictionary of keyfile parameters. Mutually exclusive with gcp_key_path.
    :param gcp_credential_config_file: File path to or content of a GCP credential configuration file.
    :param gcp_scopes: Comma-separated string containing OAuth2 scopes
    :param project_id: Project ID to read the secrets from. If not passed, the project ID from credentials
        will be used.
    :param sep: Separator used to concatenate connections_prefix and conn_id. Default: "-"
    :param impersonation_chain: Optional service account to impersonate using
        short-term credentials, or chained list of accounts required to get the
        access token of the last account in the list, which will be impersonated
        in the request. If set as a string, the account must grant the
        originating account the Service Account Token Creator IAM role. If set
        as a sequence, the identities from the list must grant Service Account
        Token Creator IAM role to the directly preceding identity, with first
        account from the list granting this role to the originating account.
    """

    def __init__(
        self,
        connections_prefix: str = "airflow-connections",
        variables_prefix: str = "airflow-variables",
        config_prefix: str = "airflow-config",
        gcp_keyfile_dict: dict | None = None,
        gcp_key_path: str | None = None,
        gcp_credential_config_file: dict[str, str] | str | None = None,
        gcp_scopes: str | None = None,
        project_id: str = PROVIDE_PROJECT_ID,
        sep: str = "-",
        impersonation_chain: str | Sequence[str] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.connections_prefix = connections_prefix
        self.variables_prefix = variables_prefix
        self.config_prefix = config_prefix
        self.sep = sep
        if connections_prefix is not None:
            if not self._is_valid_prefix_and_sep():
                raise AirflowException(
                    "`connections_prefix`, `variables_prefix` and `sep` should "
                    f"follows that pattern {SECRET_ID_PATTERN}"
                )
        try:
            if impersonation_chain:
                target_principal, delegates = _get_target_principal_and_delegates(impersonation_chain)
            else:
                target_principal = None
                delegates = None

            self.credentials, self.project_id = get_credentials_and_project_id(
                keyfile_dict=gcp_keyfile_dict,
                key_path=gcp_key_path,
                credential_config_file=gcp_credential_config_file,
                scopes=gcp_scopes,
                target_principal=target_principal,
                delegates=delegates,
            )
        except (DefaultCredentialsError, FileNotFoundError):
            log.exception(
                "Unable to load credentials for GCP Secret Manager. "
                "Make sure that the keyfile path or dictionary, credential configuration file, "
                "or GOOGLE_APPLICATION_CREDENTIALS environment variable is correct and properly configured."
            )

        # In case project id provided
        if project_id:
            self.project_id = project_id

    @property
    def client(self) -> _SecretManagerClient:
        """
        Property returning secret client.

        :return: Secrets client
        """
        return _SecretManagerClient(credentials=self.credentials)

    def _is_valid_prefix_and_sep(self) -> bool:
        prefix = self.connections_prefix + self.sep
        return _SecretManagerClient.is_valid_secret_name(prefix)

    def get_conn_value(self, conn_id: str) -> str | None:
        """
        Get serialized representation of Connection.

        :param conn_id: connection id
        """
        if self.connections_prefix is None:
            return None

        return self._get_secret(self.connections_prefix, conn_id)

    def get_variable(self, key: str) -> str | None:
        """
        Get Airflow Variable from Environment Variable.

        :param key: Variable Key
        :return: Variable Value
        """
        if self.variables_prefix is None:
            return None

        return self._get_secret(self.variables_prefix, key)

    def get_config(self, key: str) -> str | None:
        """
        Get Airflow Configuration.

        :param key: Configuration Option Key
        :return: Configuration Option Value
        """
        if self.config_prefix is None:
            return None

        return self._get_secret(self.config_prefix, key)

    def _get_secret(self, path_prefix: str, secret_id: str) -> str | None:
        """
        Get secret value from the SecretManager based on prefix.

        :param path_prefix: Prefix for the Path to get Secret
        :param secret_id: Secret Key
        """
        secret_id = self.build_path(path_prefix, secret_id, self.sep)
        return self.client.get_secret(secret_id=secret_id, project_id=self.project_id)
