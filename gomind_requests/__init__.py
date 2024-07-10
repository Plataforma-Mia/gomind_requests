import requests
from dataclasses import dataclass
import boto3
import os


@dataclass
class CustomersData:
    #informações do cliente
    id:                         str | None
    customer_id:                str | None
    office_configuration_id:    str | None
    erp_code:                   str | None 
    social_name:                str | None 
    fantasy_name:               str | None 
    document:                   str | None 
    certificate_name:           str | None 
    digital_certificate:        str | None 
    municipal_registration:     str | None
    state_registration:         str | None 
    type_tax:                   str | None 
    total_partners:             str | None

@dataclass
class OfficeConfig:
    #configurações do escritório
    id:                         str | None
    customer_id:                str | None
    office_document:            str | None
    office_description:         str | None
    usuario:                    str | None
    senha:                      str | None
    usuario_nibo:               str | None
    senha_nibo:                 str | None
    usuario_dominio:            str | None
    senha_dominio:              str | None
    diretorio:                  str | None
    destinatario_email:         str | None
    email_cc:                   str | None
    unidade_dominio:            str | None
    employer_web_user:          str | None
    employer_web_password:      str | None
    download_source:            str | None
    temp_path:                  str | None
    created_at:                 str | None
    updated_at:                 str | None
    certificate:                list | None

@dataclass
class TotalData:
    customers:  list
    config:     object   


def getOfficeData(data) -> OfficeConfig:
    return OfficeConfig(*data.values())


def getCustomerData(data) -> CustomersData:
    return CustomersData(*data.values())


def getTotalData(data, config) -> TotalData:
    return TotalData(data, config)


def getToken(url, email, passwd):
    payload = {
        'email':    str(email),
        'password': str(passwd)
    }
    response = requests.post(f'{url}/api/login', json=payload)
    
    try:
        response = response.json()['token']
    except:
        response = False

    return response


def getCustomersByRobot(url, token, id):
    header      = {"Authorization": f"Bearer {token}"}
    response    = requests.get(f'{url}/api/customers_by_robot?robot_id={id}&all_data=true', headers=header) 

    try:
        response = response.json()['customers_by_robot']
    except:
        response = False

    return response


def dataConfig(url, token, robot_id) -> CustomersData:
    dataList    = []
    data        = getCustomersByRobot(url, token, robot_id)

    if isinstance(data, str):
        return False
    try:
        config      = getOfficeData(data[0]['office_configuration'])
        toRemove    = {'office_configuration','updated_at', 'created_at'}

        for object in data:
            clientInfo  = {k: v for k, v in object.items() if k not in toRemove}
            dataList.append(getCustomerData(clientInfo))

        return getTotalData(dataList, config)
    except:
        return False


def sendCustomerEmployee(url, token, robot_id, customer_id, data):#testar
    data_keys = [
        "nome",
        "cpf",
        "pis",
        "cod_colaborador_dominio",
        "data_admissao",
        "data_demissao",
        "motivo_rescisao",
        "data_aviso",
        "tipo_aviso",
        "data_pgto"
    ]
    
    if len(data) != len(data_keys):
        print("Quantidade de campos inválida")
        return False
    
    data = dict(zip(data_keys, data))

    payload = {
        'robot_id':         f'{robot_id}',
        'customer_id':      f'{customer_id}',
        'employee_log':     data  
    }

    header      = {"Authorization": f"Bearer {token}"}
    response    = requests.post(f'{url}/api/customer_employee', json=payload, headers=header)

    try:
        response = response.json()
    except:
        response = False

    return response


def sendLog(url, token, robot_id, customer_id, data):
    data_keys = [
        "action",
        "status"
    ]

    if len(data) != len(data_keys):
        print("Quantidade de campos inválida")
        return False
    
    data = dict(zip(data_keys, data))

    payload = {
        'robot_id':     f'{robot_id}',
        'customer_id':  f'{customer_id}',
        'robot_log':    data
    }

    header      = {"Authorization": f"Bearer {token}"}
    response    = requests.post(f'{url}/api/robot_log', json=payload, headers=header) 

    try:
        response = response.json()
    except:
        response = False

    return response

def getAllLogs(url, token):
    header      = {"Authorization": f"Bearer {token}"}
    response    = requests.get(f'{url}/api/robot_log?all_data=true', headers=header) 

    try:
        response = response.json()
    except:
        response = False

    return response

def sendStap(url, token, robot_id, customer_id, data:dict):

    payload = {
        'robot_id':     f'{robot_id}',
        'customer_id':  f'{customer_id}',
        'robot_log':    data
    }

    header      = {"Authorization": f"Bearer {token}"}
    response    = requests.post(f'{url}/api/robot_log', json=payload, headers=header) 

    try:
        response = response.json()
    except:
        response = False

    return response


def getStep(url, token, robot_id, customer_id):
    data = {
        'step': 1,
        'status': 'success'
    }
    return data


def sendFilesToS3(
    files_path: str, client_id: str | int, robot_id: str | int, mes: int = None, ano: int = None, nome_empresa: str = None, s3Dir_name: str=None
) -> None:
    s3 = boto3.client("s3")
    bucket_name = "repositorio-mia"

    # Verificar se o diretório existe
    if not os.path.exists(files_path):
        print(f"O diretório {files_path} não existe.")
        return

    # Listar arquivos no diretório
    files = os.listdir(files_path)

    # Verificar se há arquivos no diretório
    if not files:
        print(f"Não há arquivos para enviar no diretório {files_path}.")
        return

    if s3Dir_name != None:
        files_path = s3Dir_name

    # Upload de arquivos para o S3
    for file in files:
        file_path = os.path.join(files_path, file)
        if mes == None or ano == None:
            s3_file_path = f"clients/{client_id}/robot/{robot_id}/{file_path}"
        else:
            s3_file_path = f"clients/{client_id}/robot/{robot_id}/{nome_empresa}/{mes}_{ano}/{file_path}"

        try:
            s3.upload_file(file_path, bucket_name, s3_file_path)
            print(
                f"Arquivo {file_path} enviado para {s3_file_path} no bucket {bucket_name}."
            )
        except Exception as e:
            print(f"Erro ao enviar {file_path} para {s3_file_path}: {e}")

    print("Envio de arquivos concluído.")

def sendFileToS3(
    file_path: str, client_id: str | int, robot_id: str | int, mes: int = None, ano: int = None, nome_empresa: str = None
) -> None:
    s3 = boto3.client("s3")
    bucket_name = "repositorio-mia"

    # Verificar se o diretório existe
    if not os.path.exists(file_path):
        print(f"O diretório {file_path} não existe.")
        return

    # Verificar se há arquivos no diretório
    if not os.path.isfile(file_path):
        print(f"Não há arquivos para enviar no diretório {file_path}.")
        return

    # Upload de arquivo para o S3
    if mes == None or ano == None:
        s3_file_path = f"clients/{client_id}/robot/{robot_id}/{file_path}"
    else:
        s3_file_path = f"clients/{client_id}/robot/{robot_id}/{nome_empresa}/{mes}_{ano}/{file_path}"

    try:
        s3.upload_file(file_path, bucket_name, s3_file_path)
        print(
            f"Arquivo {file_path} enviado para {s3_file_path} no bucket {bucket_name}."
        )
    except Exception as e:
        print(f"Erro ao enviar {file_path} para {s3_file_path}: {e}")

    print("Envio de arquivos concluído.")