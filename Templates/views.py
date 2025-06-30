"""
Copyright © 2022–2023 Riverstone Infotech. All rights reserved.

CORPDESIGN Order and all related materials, including but not limited to text, graphics, 
logos, images, and software, are protected by copyright and other intellectual 
property laws. Reproduction, distribution, display, or modification of any of the 
content for any purpose without express written permission from Riverstone Infotech 
is prohibited.

For permissions and inquiries, please contact:
software@riverstonetech.com

Unauthorized use or reproduction of CORPDESIGN Order may result in legal action.
"""
from jinja2 import Template

from jinja2 import Template

def render_purchase_order_summary(progress: list) -> str:
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Purchase Order Reports</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 20px;
            }
            table { 
                width: 100%;
                border-collapse: collapse; 
                margin-top: 10px;}
            th, td {
                border: 2px solid #000;
                padding: 10px;
                text-align: left;
            }
            th {
                border: 1px solid #ddd;
                padding: 8px; 
                text-align: center;
                background-color: #f4f4f4;
            }
            .status-success {
                color: green;
                font-weight: bold;
            }
            .status-error {
                color: red;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <h1>Purchase Order Reports Summary (Test): {{ progress|length }} Total Files</h1>
        <hr>

        {% for entry in progress %}
        <div class="summary">
            <table>
                <tr>
                    <td style="padding: 8px; text-align: left;", colspan="3">
                        <strong>File:</strong> {{ entry.filename }},
                        <strong>Status:</strong> {{ entry.result.status }}
                        {% if entry.result.statusCode == 200 %}
                            ,{{ entry.success }}/{{ entry.total }} processed, 
                            {{ entry.failure }}/{{ entry.total }} Errors
                        {% elif entry.result.statusCode == 400 or entry.result.statusCode ==404 %}
                         , <strong>Message:</strong> {{entry.result.message.replace('_',' ')}} 
                        {% else %} 
                            , <strong>Message:</strong> Internal error encountered. Please contact the administrator for assistance.
                        {% endif %}
                    </td>
                </tr>
            </table>
        </div>
        {% endfor %}

        {% for entry in progress %}
        {% if entry.result.statusCode == 200 %}
        <div class="report-section">
            <h2>File: {{ entry.filename }}</h2>
            {% if entry.result is string %}
                <p><strong>Message:</strong> {{ entry.result }}</p>
            {% else %}
                <table>
                    <tr>
                        <td style="border: 1px solid #ddd; padding: 8px; text-align: left;", colspan="3">
                            <strong>File:</strong> {{ entry.filename }},
                            <strong>Status:</strong> {{ entry.result.status }}
                            {% if entry.result.statusCode == 200 %}
                                ({{ entry.success }}/{{ entry.total }} processed, 
                                {{ entry.failure }}/{{ entry.total }} Errors)
                            {% endif %}
                        </td>
                    </tr>
                    {% if entry.result.statusCode == 200 %}
                    <tr>
                        <td style="border: 1px solid #ddd; padding: 8px; text-align: left;", colspan="3">
                            <p><strong>Customer Name:</strong> {{ entry.result.customer_name }}</p>
                            <p><strong>Message:</strong> {{ entry.result.message }}</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="border: 1px solid #ddd; padding: 8px; text-align: left;"><strong>Purchase Order:</strong> {{ entry.result.purchase_order }}</td>
                        <td style="border: 1px solid #ddd; padding: 8px; text-align: left;">
                            <strong>Sales Order Number:</strong> {{ entry.result.orderNumber }} -
                            <a href="{{ entry.result.orderUrl }}">NetSuite {{ entry.result.orderNumber }}</a>
                        </td>
                        <td style="border: 1px solid #ddd; padding: 8px; text-align: left;"><strong>Invoice Date:</strong> {{ entry.result.invoice_date }}</td>
                    </tr>
                    <tr>
                        {% for label, address in {'Shipping Address': entry.result.shipping_address, 'Billing Address': entry.result.billing_address}.items() %}
                        <td style="border: 1px solid #ddd; padding: 8px; text-align: left; vertical-align: top;">
                            <h3>{{ label }}:</h3>
                            {% if address is mapping %}
                                <ul>
                                    {% for key, value in address.items() %}
                                        <li><strong>{{ key.replace('_', ' ').title() }}:</strong> {{ value }}</li>
                                    {% endfor %}
                                </ul>
                            {% elif address is iterable and address is not string %}
                                {% for addr in address %}
                                    <ul>
                                        {% for key, value in addr.items() %}
                                            <li><strong>{{ key.replace('_', ' ').title() }}:</strong> {{ value }}</li>
                                        {% endfor %}
                                    </ul>
                                {% endfor %}
                            {% elif address %}
                                <p>{{ address }}</p>
                            {% else %}
                                <p>Not Available</p>
                            {% endif %}
                        </td>
                        {% endfor %}
                        
                    </tr>
                    <tr>
                        <td style="border: 1px solid #ddd; padding: 8px;", colspan="3">
                            <p><strong>Details:</strong></p>
                            <table>
                                <tr>
                                    <th style="border: 1px solid #ddd; padding: 8px; text-align: center; background-color: #f4f4f4;">PO Product Code</th>                                
                                    <th style="border: 1px solid #ddd; padding: 8px; text-align: center; background-color: #f4f4f4;">Netsuite Product Code</th>
                                    <th style="border: 1px solid #ddd; padding: 8px; text-align: center; background-color: #f4f4f4;">PO Description</th>
                                    <th style="border: 1px solid #ddd; padding: 8px; text-align: center; background-color: #f4f4f4;">Qty</th>
                                    <th style="border: 1px solid #ddd; padding: 8px; text-align: center; background-color: #f4f4f4;">Unit Price</th>
                                    <th style="border: 1px solid #ddd; padding: 8px; text-align: center; background-color: #f4f4f4;">Amount</th>
                                    <th style="border: 1px solid #ddd; padding: 8px; text-align: center; background-color: #f4f4f4;">NetSuite</th>
                                    <th style="border: 1px solid #ddd; padding: 8px; text-align: center; background-color: #f4f4f4;">Reason</th>
                                    <th style="border: 1px solid #ddd; padding: 8px; text-align: center; background-color: #f4f4f4;">Comment</th>
                                    
                                </tr>
                                {% for item in entry.result.order_line_items %}
                                    <tr>
                                        <td style="border: 1px solid #ddd; padding: 8px; text-align: left;">{{ item.pdf_product_code }}</td>                                    
                                        <td style="border: 1px solid #ddd; padding: 8px; text-align: left;">{{ item.product_code }}</td>
                                        <td style="border: 1px solid #ddd; padding: 8px; text-align: left;">{{ item.description }}</td>
                                        
                                        <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{{ item.qty }}</td>
                                        <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{{ item.unit_price }}</td>
                                        <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{{ item.amount }}</td>
                                          <td style="border: 1px solid #ddd; padding: 8px; text-align: left;" class="{% if item.status in ['inserted', 'success'] %}status-success{% else %}status-error{% endif %}">
                                            {% if item.status == 'not available' %}
                                                Error
                                            {% else %}
                                                {{ item.netsuite_status.title() }}
                                            {% endif %}
                                        </td>
                                        <td style="border: 1px solid #ddd; padding: 8px; text-align: left;">
                                            {% if item.status == 'not available' %}
                                                <center>SKU Not Found</center>
                                            {% else %}
                                                <center>-</center>
                                            {% endif %}
                                            </td>
                                        <td style="border: 1px solid #ddd; padding: 8px; text-align: left;" >
                                            {% set unavailable_items = [] %}
                                            
                                            {% if item.availableQuantity == 0 %}
                                                {% set _ = unavailable_items.append(item.product_code ~ " has 0 availability") %}
                                            {% endif %}
                                            
                                            {% if item.components %}
                                                {% for comp in item.components %}
                                                    {% if comp.availableQuantity == 0 %}
                                                        {% set _ = unavailable_items.append(comp.productCode ~ " has 0 availability") %}
                                                    {% endif %}
                                                {% endfor %}
                                            {% endif %}
                                            
                                            {% if unavailable_items %}
                                                <ul>
                                                    {% for msg in unavailable_items %}
                                                        <li>{{ msg }}</li>
                                                    {% endfor %}
                                                </ul>
                                            {% else %}
                                                <center>-</center>
                                            {% endif %}
                                        </td>

                                    </tr>
                                {% endfor %}
                            </table>
                        </td>
                    </tr>
                    {% endif %}
                </table>
            {% endif %}
        </div>
          {% endif %}
        {% endfor %}
    </body>
    </html>
    """

    template = Template(html_template)
    return template.render(progress=progress)


def render_no_valid_attachments_message() -> str:
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>No Valid Attachments</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 20px;
                text-align: center;
            }
            .message {
               
                font-weight: bold;
                margin-top: 50px;
            }
        </style>
    </head>
    <body>
        <p class="message">No valid attachments were provided. Please upload files with the following extensions: .pdf, .xls, .xlsx.</p>
    </body>
    </html>
    """
    template = Template(html_template)
    return template.render()