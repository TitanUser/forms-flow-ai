"""This exposes application service."""

from datetime import datetime
from functools import lru_cache
from http import HTTPStatus

from flask import current_app

from formsflow_api.exceptions import BusinessException
from formsflow_api.models import Application, FormProcessMapper

from formsflow_api.schemas import (
    AggregatedApplicationSchema,
    ApplicationSchema,
    FormProcessMapperSchema,
)

from formsflow_api.services.external import BPMService
from formsflow_api.utils import NEW_APPLICATION_STATUS


class ApplicationService:
    """This class manages application service."""

    @staticmethod
    def create_application(data, token):
        """Create new application."""
        data["application_status"] = NEW_APPLICATION_STATUS

        mapper = FormProcessMapper.find_form_by_form_id(data["form_id"])
        data["form_process_mapper_id"] = mapper.id
        data["application_name"] = mapper.form_name
        application = Application.create_from_dict(data)
        if "process_instance_id" in data:
            application.update({"process_instance_id": data["process_instance_id"]})
        else:
            payload = {
                "variables": {
                    "applicationId": {"value": application.id},
                    "formUrl": {"value": application.form_url},
                    "formName": {"value": application.application_name},
                    "submitterName": {"value": application.created_by},
                    "submissionDate": {"value": application.created.__str__()},
                }
            }
            try:
                camunda_start_task = BPMService.post_process_start(
                    process_key=mapper.process_key, payload=payload, token=token
                )
                application.update({"process_instance_id": camunda_start_task["id"]})
            except TypeError as camunda_error:
                response = {
                    "message": "Camunda workflow not able to create a task",
                    "error": camunda_error,
                }
                current_app.logger.critical(response)
                return response, HTTPStatus.BAD_GATEWAY
            except BaseException as application_err:
                response = {
                    "systemErrors": application_err,
                    "message": "Camunda Process Mapper Key not provided",
                }, HTTPStatus.BAD_REQUEST
                current_app.logger.warning(response)
                return response
        return application

    @staticmethod
    @lru_cache(maxsize=32)
    def get_authorised_form_list(token):
        """Function to get the authorized forms based on token passed.
        Used LRU cache to memoize results and parameter maxsize defines
        the no of function calls."""
        response = BPMService.get_auth_form_details(token=token)
        return response

    @staticmethod
    def get_auth_applications_and_count(
        token: str,
        page_no: int,
        limit: int,
        order_by: str,
        created_from: datetime,
        created_to: datetime,
        modified_from: datetime,
        modified_to: datetime,
        application_id: int,
        application_name: str,
        application_status: str,
        created_by: str,
        sort_order: str,
    ):
        """Get applications only from authorized groups."""
        if page_no:
            page_no = int(page_no)
        if limit:
            limit = int(limit)
        if order_by:
            order_by = str(order_by)
        if application_id:
            application_id = int(application_id)
        if application_name:
            application_name = str(application_name)
        if application_status:
            application_status = str(application_status)
        if created_by:
            created_by = str(created_by)

        if sort_order:
            sort_order = str(sort_order)

        auth_form_details = ApplicationService.get_authorised_form_list(token=token)
        form_names = []
        application_schema = ApplicationSchema()
        if auth_form_details:
            for auth_form_detail in auth_form_details:
                form_names.append(auth_form_detail["formName"])
            applications, get_all_applications_count = Application.find_by_form_names(
                form_names=form_names,
                application_id=application_id,
                application_name=application_name,
                application_status=application_status,
                created_by=created_by,
                page_no=page_no,
                limit=limit,
                order_by=order_by,
                modified_from=modified_from,
                modified_to=modified_to,
                sort_order=sort_order,
                created_from=created_from,
                created_to=created_to,
            )

            return (
                application_schema.dump(applications, many=True),
                get_all_applications_count,
            )
        else:
            return (application_schema.dump([], many=True), 0)

    @staticmethod
    def get_auth_by_application_id(application_id: int, token: str):
        """Get authorized Application by id."""
        auth_form_details = ApplicationService.get_authorised_form_list(token=token)
        application_schema = ApplicationSchema()
        if auth_form_details:
            form_names = []
            for auth_form_detail in auth_form_details:
                form_names.append(auth_form_detail["formName"])

            application = Application.find_id_by_form_names(
                form_names=form_names, application_id=application_id
            )
            return application_schema.dump(application), HTTPStatus.OK
        else:
            return (application_schema.dump([])), HTTPStatus.FORBIDDEN

    @staticmethod
    def get_all_applications(page_no: int, limit: int):
        """Get all applications."""
        if page_no:
            page_no = int(page_no)
        if limit:
            limit = int(limit)

        applications = Application.find_all(page_no=page_no, limit=limit)
        application_schema = ApplicationSchema()
        return application_schema.dump(applications, many=True)

    @staticmethod
    def get_all_applications_by_user(
        user_id: str,
        page_no: int,
        limit: int,
        order_by: str,
        sort_order: str,
        created_from: datetime,
        created_to: datetime,
        modified_from: datetime,
        modified_to: datetime,
        created_by: str,
        application_status: str,
        application_name: str,
        application_id: int,
    ):
        """Get all applications based on user."""
        if page_no:
            page_no = int(page_no)
        if limit:
            limit = int(limit)
        if order_by:
            order_by = str(order_by)
        if sort_order:
            sort_order = str(sort_order)
        if application_id:
            application_id = int(application_id)
        if application_name:
            application_name = str(application_name)
        if application_status:
            application_status = str(application_status)
        if created_by:
            created_by = str(created_by)

        applications, get_all_applications_count = Application.find_all_by_user(
            user_id=user_id,
            page_no=page_no,
            limit=limit,
            order_by=order_by,
            sort_order=sort_order,
            application_id=application_id,
            application_name=application_name,
            application_status=application_status,
            created_by=created_by,
            modified_from=modified_from,
            modified_to=modified_to,
            created_from=created_from,
            created_to=created_to,
        )
        application_schema = ApplicationSchema()

        return (
            application_schema.dump(applications, many=True),
            get_all_applications_count,
        )

    @staticmethod
    def get_all_application_by_user_group(page_no: int, limit: int, user_id: str):
        if page_no:
            page_no = int(page_no)
        if limit:
            limit = int(limit)
        applications = Application.find_all_by_user_group(
            user_id=user_id, page_no=page_no, limit=limit
        )
        application_schema = ApplicationSchema()
        return application_schema.dump(applications, many=True)

    @staticmethod
    def get_all_applications_ids(application_ids):
        applications = Application.find_by_ids(application_ids=application_ids)
        application_schema = ApplicationSchema()
        return application_schema.dump(applications, many=True)

    @staticmethod
    def get_all_application_count(
        token: str,
        page_no: int,
        limit: int,
    ):
        """Get application count."""
        if page_no:
            page_no = int(page_no)
        if limit:
            limit = int(limit)
        auth_form_details = ApplicationService.get_authorised_form_list(token=token)
        form_names = []
        application_schema = ApplicationSchema()
        if auth_form_details:
            for auth_form_detail in auth_form_details:
                form_names.append(auth_form_detail["formName"])
            applications = Application.find_all_applications(
                form_names=form_names, page_no=page_no, limit=limit
            )
            return (
                application_schema.dump(applications, many=True),
                applications.count(),
            )
        else:
            return (application_schema.dump([], many=True), 0)

    @staticmethod
    def get_all_application_by_user_count(user_id: str):
        """Get application count."""
        return Application.find_all_by_user_count(user_id=user_id)

    @staticmethod
    def get_all_application_status():
        """Get all application status"""
        status_list = Application.find_all_application_status()
        status_list = [x.application_status for x in status_list]
        current_app.logger.debug(status_list)
        return {"applicationStatus": status_list}

    @staticmethod
    def get_all_applications_form_id(form_id, page_no: int, limit: int):
        """Get all applications."""
        if page_no:
            page_no = int(page_no)
        if limit:
            limit = int(limit)

        applications = Application.find_by_form_id(
            form_id=form_id, page_no=page_no, limit=limit
        )
        application_schema = ApplicationSchema()
        return application_schema.dump(applications, many=True)

    @staticmethod
    def get_all_applications_form_id_user(
        form_id, user_id: str, page_no: int, limit: int  # pylint: disable=C0330
    ):
        """Get all applications."""
        if page_no:
            page_no = int(page_no)
        if limit:
            limit = int(limit)

        applications = Application.find_by_form_id_user(
            form_id=form_id, user_id=user_id, page_no=page_no, limit=limit
        )
        application_schema = ApplicationSchema()
        return application_schema.dump(applications, many=True)

    @staticmethod
    def get_all_applications_form_id_count(form_id):
        """Get application count."""
        return Application.find_all_by_form_id_count(form_id=form_id)

    @staticmethod
    def get_all_applications_form_id_user_count(form_id, user_id):
        """Get application count."""
        return Application.find_all_by_form_id_user_count(
            form_id=form_id, user_id=user_id
        )

    @staticmethod
    def get_application(application_id: int):
        """Get application by id."""
        return ApplicationSchema().dump(
            Application.find_by_id(application_id=application_id)
        )

    @staticmethod
    def get_application_by_user(application_id: int, user_id: str):
        """Get application by user id"""
        application = Application.find_id_by_user(
            application_id=application_id, user_id=user_id
        )
        if application:
            return ApplicationSchema().dump(application), HTTPStatus.OK
        else:
            return ApplicationSchema().dump([]), HTTPStatus.FORBIDDEN

    @staticmethod
    def update_application(application_id: int, data):
        """Update application."""
        application = Application.find_by_id(application_id=application_id)
        if application:
            application.update(data)
        else:
            raise BusinessException("Invalid application", HTTPStatus.BAD_REQUEST)

    @staticmethod
    def get_aggregated_applications(from_date: str, to_date: str):
        """Get aggregated applications."""
        applications = Application.find_aggregated_applications(
            from_date=from_date, to_date=to_date
        )
        schema = AggregatedApplicationSchema(exclude=("application_status",))
        return schema.dump(applications, many=True)

    @staticmethod
    def get_current_aggregated_applications(from_date: datetime, to_date: datetime):
        """Get aggregated applications."""
        applications = Application.find_aggregated_applications_modified(
            from_date=from_date, to_date=to_date
        )
        schema = AggregatedApplicationSchema(exclude=("application_status",))
        return schema.dump(applications, many=True)

    @staticmethod
    def get_aggregated_application_status(
        mapper_id: int, from_date: datetime, to_date: datetime
    ):
        """Get aggregated application status."""
        application_status = Application.find_aggregated_application_status(
            mapper_id=mapper_id, from_date=from_date, to_date=to_date
        )
        schema = AggregatedApplicationSchema(exclude=("form_process_mapper_id",))
        return schema.dump(application_status, many=True)

    @staticmethod
    def get_current_aggregated_application_status(
        mapper_id: int, from_date: str, to_date: str
    ):
        """Get aggregated application status."""
        application_status = Application.find_aggregated_application_status_modified(
            mapper_id=mapper_id, from_date=from_date, to_date=to_date
        )
        schema = AggregatedApplicationSchema(exclude=("form_process_mapper_id",))
        return schema.dump(application_status, many=True)

    @staticmethod
    def get_application_form_mapper_by_id(application_id: int):
        """Get form process mapper."""
        mapper = FormProcessMapper.find_by_application_id(application_id=application_id)
        if mapper:
            mapper_schema = FormProcessMapperSchema()
            return mapper_schema.dump(mapper)

        raise BusinessException("Invalid application", HTTPStatus.BAD_REQUEST)

    @staticmethod
    def apply_custom_attributes(application_schema):
        """Wrapper function to call Application Schema Wrapper"""
        if isinstance(application_schema, list):
            for entry in application_schema:
                ApplicationSchemaWrapper.apply_attributes(entry)
        else:
            ApplicationSchemaWrapper.apply_attributes(application_schema)
        return application_schema


class ApplicationSchemaWrapper:
    """ApplicationSchemaWrapper Class"""

    @staticmethod
    def apply_attributes(application):
        """Wrapper function to call Application Schema Wrapper class
        to find formid, submissionid from passed formUrl
        """
        try:
            formurl = application["formUrl"]
            application["formId"] = formurl[
                formurl.find("/form/") + 6 : formurl.find("/submission/")
            ]
            application["submissionId"] = formurl[
                formurl.find("/submission/") + 12 : len(formurl)
            ]
            return application
        except KeyError as err:
            return (
                "The required fields of Input request are not passed",
                HTTPStatus.BAD_REQUEST,
            )
