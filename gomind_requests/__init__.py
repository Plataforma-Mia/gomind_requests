import requests
from dataclasses import dataclass, fields
import boto3
import os
from pathlib import Path
import zipfile
import re
import gomind_cli as cli
from datetime import datetime
import sys
from dotenv import load_dotenv
import gomind_cli as cli
import shutil
import gomind_sqlite_to_excel as sql2excel
try:
    from logger import logger
except:
    class Logger:
        def log(self, message, status="info"):
            print("{} - [{}]".format(message, status))

    logger = Logger()
    
CLI_ARGUMENTS = cli.get_sys_args_as_dict()

start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

load_dotenv()
user        = os.getenv('MIA_LOGIN')
passwd      = os.getenv('MIA_PASSWORD')
url         = os.getenv('MIA_URL')
ANO_MIA     = CLI_ARGUMENTS.get("competenceMonth")
MES_MIA     = CLI_ARGUMENTS.get("competenceYear")
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
    inner_sheet:                str | bool | None
    payment_date:               str | None
    city_hall_login:            str | None
    city_hall_password:         str | None  
    city_hall_login_2:          str | None
    city_hall_password_2:       str | None  
    employer_web_user:          str | None  
    employer_web_password:      str | None
    apuration_regime:           str | None


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
    procuration_user:           str | None
    procuration_password:       str | None
    #diretorio:                  str | None
    destinatario_email:         str | None
    email_cc:                   str | None
    #unidade_dominio:            str | None
    #employer_web_user:          str | None
    #employer_web_password:      str | None
    download_source:            str | None
    #temp_path:                  str | None
    created_at:                 str | None
    updated_at:                 str | None
    certificate:                list | None

    # Mapeamento dos campos de config da API (API -> OfficeConfig)
    # Acrescentar campos com nomes diferentes aquiv
    field_mapping = {
        'email':            'usuario',
        'password':         'senha',
        'nibo_login':       'usuario_nibo',
        'nibo_password':    'senha_nibo',
        'dominio_user':     'usuario_dominio',
        'dominio_password': 'senha_dominio',
        'recipient_email':  'destinatario_email',
        'copy_email':       'email_cc',
    }

@dataclass
class TotalData:
    customers:  list
    config:     object   


def getOfficeData(data) -> OfficeConfig:
    valid_fields    = {field.name for field in fields(OfficeConfig)}
    mapped_data     = {}
    
    for api_field, value in data.items():
        # Checar se tem mapeamento para esse campo
        if api_field in OfficeConfig.field_mapping:
            dataclass_field = OfficeConfig.field_mapping[api_field]
            mapped_data[dataclass_field] = value
        # Se nenhum mapeamento existir, tentar usar nome original
        elif api_field in valid_fields:
            mapped_data[api_field] = value
    
    return OfficeConfig(**mapped_data)


def getCustomerData(data) -> CustomersData:
    dataclass_fields = {field.name for field in fields(CustomersData)}
    filtered_data = {k: v for k, v in data.items() if k in dataclass_fields}
    return CustomersData(**filtered_data)


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


def getCustomersByRobot(url, token, robot_id, customer_id):
    header      = {"Authorization": f"Bearer {token}"}
    response    = requests.get(f'{url}/api/customers_by_robot?robot_id={robot_id}&customer_id={customer_id}&all_data=true', headers=header) 
    logger.log(f'{url}/api/customers_by_robot?robot_id={robot_id}&customer_id={customer_id}&all_data=true')
    logger.log('Passou no requests.get para customers_by_robot')
    try:
        response = response.json()['children_customers']
        if isinstance(response, list) and not response:
            logger.log('A resposta de getCustomersByRobot() é uma lista vazia. Não existem clientes associados ao robô.')
    except Exception as e:
        logger.log(f'erro em getCustomersByRobot(): {e}')
        response = False

    return response

def getRobotNameById(url, token, robot_id, customer_id):
    header      = {"Authorization": f"Bearer {token}"}
    response    = requests.get(f'{url}/api/robots?customer_id={customer_id}6&all_data=true', headers=header)
    
    try:
        data = response.json().get('robots', {}).get('data', [])
        for robot in data:
            if robot.get('id') == robot_id:
                return robot.get('description')
    except:
        return False


def getRobotCodeById(url, token, robot_id, customer_id):
    header      = {"Authorization": f"Bearer {token}"}
    response    = requests.get(f'{url}/api/robots?customer_id={customer_id}6&all_data=true', headers=header)
    
    try:
        data = response.json().get('robots', {}).get('data', [])
        for robot in data:
            if robot.get('id') == robot_id:
                return robot.get('name')
    except:
        return False


def dataConfig(url, token, robot_id, customer_id) -> CustomersData:
    dataList    = []
    data        = getCustomersByRobot(url, token, robot_id, customer_id)
    if isinstance(data, str):
        logger.log(data)
        logger.log("Erro ao buscar dados do cliente")
        return False
    if isinstance(data, list) and not data:
        logger.log('A resposta de dataConfig() é uma lista vazia. Verifique a associação do cliente com o tobô.')
    try:
        logger.log('Entrou no try/exc do dataConfig()')

        config     = getOfficeData(data[0]['office_configuration'])
        cert       = []

        logger.log(f'definiu config: {config} e abriu lista para cert')

        for object in data:
            try:
                aux  = object['office_configuration']['certificate']
                aux['certificate_name']  = object['office_configuration']['office_description']
                cert.append(aux)
            except:
                pass
        
        logger.log(f'criou lista de certificados: {cert}')

        config.certificate = remove_duplicates(cert)
        toRemove    = {'office_configuration','updated_at', 'created_at', 'robot'}
        
        clients_id = CLI_ARGUMENTS.get("customers", [])

        for object in data:
            
            if len(clients_id) != 0  and object['id'] not in clients_id:
                continue

            clientInfo  = {k: v for k, v in object.items() if k not in toRemove}
            clientInfo['municipal_registration'] = removeNonAlphanumeric(clientInfo['municipal_registration'])
            emptyStringToNone(clientInfo)
            dataList.append(getCustomerData(clientInfo))

        return getTotalData(dataList, config)
    
    except Exception as e:
        logger.log(f'erro em dataConfig(): {e}')
        return False
    
def remove_duplicates(list_of_dicts):
    seen = set()
    unique_dicts = []
    
    for d in list_of_dicts:
        if d is not None:
            items_tuple = tuple(d.items())
            if items_tuple not in seen:
                seen.add(items_tuple)
                unique_dicts.append(d)
    
    return unique_dicts

def removeNonAlphanumeric(string:str | None) -> str | None:
    if not string:
        return None
    return re.sub(r'\W+', '', string)

def emptyStringToNone(dict:dict) -> dict:
    for chave, string in dict.items():
        if string is str:
            dict[chave] = string.strip
        if string == '':
            dict[chave] = None
    return dict
        
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
        logger.log("Quantidade de campos inválida")
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
        logger.log("Quantidade de campos inválida")
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


def getStep(url: str, token: str, robot_id: int|str, customer_id: int|str, erp_code: int|str|None = None) -> str | bool:

    header      = {"Authorization": f"Bearer {token}"}

    if erp_code != None:
        response    = requests.get(f'{url}/api/robot_step_log?robot_id={robot_id}&customer_id={customer_id}&erp_code={erp_code}', headers=header) 
    else:
        response    = requests.get(f'{url}/api/robot_step_log?robot_id={robot_id}&customer_id={customer_id}', headers=header)
   
    try:
        competence = str(response.json()['robot_log']['data'][0]['robot_log']['competence_month']) + '/' + str(response.json()['robot_log']['data'][0]['robot_log']['competence_year'])
        response = str(response.json()['robot_log']['data'][0]['robot_log']['step'])
    except:
        return False

    return response, competence


def sendFilesToS3(
    files_path: str, client_id: str | int, robot_id: str | int, mes: int = None, ano: int = None, nome_empresa: str = None, s3Dir_name: str=None
) -> str|None:
    s3 = boto3.client("s3")
    bucket_name = os.getenv('BUCKET_NAME')

    if not bucket_name:
        raise ValueError("Variável de ambiente BUCKET_NAME não definida.")

    # Verificar se o diretório existe
    if not os.path.exists(files_path):
        logger.log(f"O diretório {files_path} não existe.")
        return

    # Listar arquivos no diretório
    files = os.listdir(files_path)

    # Verificar se há arquivos no diretório
    if not files:
        logger.log(f"Não há arquivos para enviar no diretório {files_path}.")
        return
    
    # Upload de arquivos para o S3
    for file in files:
        file_path = os.path.join(files_path, file)       
        if mes == None or ano == None and s3Dir_name != None:
            s3_file_path = f"clients/{client_id}/robot/{robot_id}/{s3Dir_name}/{file}"
        elif mes == None or ano == None:
            s3_file_path = f"clients/{client_id}/robot/{robot_id}/{file}"
        elif s3Dir_name != None:
            s3_file_path = f"clients/{client_id}/robot/{robot_id}/{nome_empresa}/{mes}_{ano}/{s3Dir_name}/{file}"
        else:
            s3_file_path = f"clients/{client_id}/robot/{robot_id}/{nome_empresa}/{mes}_{ano}/{file}"

        try:
            s3.upload_file(file_path, bucket_name, s3_file_path)
            logger.log(
                f"Arquivo {file_path} enviado para {s3_file_path} no bucket {bucket_name}."
            )
        except Exception as e:
            logger.log(f"Erro ao enviar {file_path} para {s3_file_path}: {e}")

    logger.log("Envio de arquivos concluído.")
    return s3_file_path

def sendFileToS3(
    file_path: str, client_id: str | int, robot_id: str | int, mes: int = None, ano: int = None, nome_empresa: str = None, s3Dir_name: str=None
) -> str|None:
    s3 = boto3.client("s3")
    bucket_name = os.getenv('BUCKET_NAME')

    if not bucket_name:
        raise ValueError("Variável de ambiente BUCKET_NAME não definida.")

    # Verificar se o diretório existe
    if not os.path.exists(file_path):
        logger.log(f"O diretório {file_path} não existe.")
        return

    # Verificar se há arquivos no diretório
    if not os.path.isfile(file_path):
        logger.log(f"Não há arquivos para enviar no diretório {file_path}.")
        return

    file_name = os.path.basename(file_path)

    # Upload de arquivo para o S3
    if (mes == None or ano == None) and s3Dir_name != None:
        s3_file_path = f"clients/{client_id}/robot/{robot_id}/{s3Dir_name}/{file_name}"
    elif mes == None or ano == None:
        s3_file_path = f"clients/{client_id}/robot/{robot_id}/{file_name}"
    elif s3Dir_name != None:
        s3_file_path = f"clients/{client_id}/robot/{robot_id}/{nome_empresa}/{mes}_{ano}/{s3Dir_name}/{file_name}"
    else:
        s3_file_path = f"clients/{client_id}/robot/{robot_id}/{nome_empresa}/{mes}_{ano}/{file_name}"

    try:
        s3.upload_file(file_path, bucket_name, s3_file_path)
        logger.log(
            f"Arquivo {file_path} enviado para {s3_file_path} no bucket {bucket_name}."
        )
    except Exception as e:
        logger.log(f"Erro ao enviar {file_path} para {s3_file_path}: {e}")

    logger.log("Envio de arquivos concluído.")
    return s3_file_path

def getFileFromS3(
    local_file_path: str, s3_file_path: str, client_id: str | int, robot_id: str | int, mes: int = None, ano: int = None, nome_empresa: str = None
) -> None:
    
    s3              = boto3.client("s3")
    file_name       = os.path.basename(s3_file_path)
    local_file_path = os.path.join(local_file_path, file_name)

    bucket_name = os.getenv('BUCKET_NAME')

    if not bucket_name:
        raise ValueError("Variável de ambiente BUCKET_NAME não definida.")

    # Upload de arquivo para o S3
    if mes == None or ano == None:
        s3_file_path_new = f"clients/{client_id}/robot/{robot_id}/{file_name}"
    else:
        s3_file_path_new = f"clients/{client_id}/robot/{robot_id}/{nome_empresa}/{mes}_{ano}/{file_name}"

    try:
        s3.download_file(bucket_name, s3_file_path_new, local_file_path)
        logger.log(
            f"Arquivo {s3_file_path_new} enviado para {local_file_path}."
        )
    except Exception as e:
        logger.log(f"Erro ao baixar {s3_file_path_new} para {local_file_path}: {e}")
        return

    logger.log("Download de arquivos concluído.")


def list_s3_objects(bucket: str, prefix: str, filter_pfx: bool = False) -> list:
    """
    Lista objetos em um bucket S3 dado um prefixo.
    Se filter_pfx for True, retorna apenas arquivos com a extensão .pfx.
    """
    try:
        s3 = boto3.client("s3")
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        objects = response.get("Contents", [])
        
        if filter_pfx:
            objects = [obj for obj in objects if obj["Key"].endswith('.pfx')]
        
        return [obj["Key"] for obj in objects if obj["Key"] != prefix]
    except Exception as e:
        logger.log(f"Erro ao listar objetos do S3: {e}")
        return []


def download_s3_objects(bucket: str, objects: list, local_dir: Path):
    """
    Baixa objetos do S3 para um diretório local.
    """
    for obj in objects:
        file_name = Path(obj).name
        file_path = local_dir / file_name

        logger.log(f"Baixando {obj} para {file_path}")

        try:
            s3 = boto3.client("s3")
            s3.download_file(bucket, obj, str(file_path))
        except Exception as e:
            logger.log(f"Erro ao baixar {obj}: {e}")


def get_instance_id():
    #Obtém o ID da instância EC2
    response = requests.get("http://169.254.169.254/latest/meta-data/instance-id")
    return response.text

def terminate_instance():
    #Terminate the EC2 instance
    instance_id = get_instance_id()
    ec2_client  = boto3.client("ec2", region_name="sa-east-1")
    ec2_client.terminate_instances(InstanceIds=[instance_id])


def download_file(s3, bucket, s3_key, local_path):

    if not os.path.exists(os.path.dirname(local_path)):
        os.makedirs(os.path.dirname(local_path))
    s3.download_file(bucket, s3_key, local_path)

def s3_dowloadAll(client_id:int|str, robot_id:int|str, local_directory:str, competencia:str='', to_ignore:list = []) -> str|bool:
    try:

        local_directory = os.path.join(local_directory,'s3_download')

        # bucket_name       = 'repositorio-mia'
        s3_prefix         = f'clients/{client_id}/robot/{robot_id}/'
        bucket_name = os.getenv('BUCKET_NAME')

        if not bucket_name:
            raise ValueError("Variável de ambiente BUCKET_NAME não definida.")

        # Cria a sessão e o cliente S3
        s3 = boto3.client('s3')

        # Lista todos os objetos no bucket com o prefixo especificado
        paginator   = s3.get_paginator('list_objects_v2')
        pages       = paginator.paginate(Bucket=bucket_name, Prefix=s3_prefix)

        # Itera sobre os arquivos e faz o download recursivo
        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:

                    s3_key = obj['Key']
                    relative_path = os.path.relpath(s3_key, s3_prefix)
                    local_file_path = os.path.join(local_directory, relative_path)
                    
                    default_ignore    = [f'logs{os.sep}', 'arquivos_baixados.zip']
                    to_ignore         = to_ignore + default_ignore

                    if any(ignore_str in relative_path for ignore_str in to_ignore):
                        continue
                    
                    if  competencia not in relative_path:
                        continue

                    download_file(s3, bucket_name, s3_key, local_file_path)
                    logger.log(f'Arquivo {s3_key} baixado para {local_file_path}')

        return local_directory
    except:
        return False

def zip_directory(folder_path, output_filename):
    with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.relpath(file_path, folder_path))

#colocar data correta no arquivo
def get_s3_zip(client_id:int|str, robot_id:int|str, local_directory:str, competencia:str = '', to_ignore:list = []) -> str|bool:
    try:
        dir = s3_dowloadAll(client_id, robot_id, local_directory, competencia, to_ignore)
        current_date    = datetime.now().strftime('%Y%m%H%M%S')
        competence      = str(CLI_ARGUMENTS.get('competenceMonth')) + '_' + str(CLI_ARGUMENTS.get('competenceYear'))
        token           = getToken(url, user, passwd)
        robotName       = getRobotCodeById(url, token, robot_id, client_id)
        if not robotName:
            robotName = 'arquivos_baixados'

        zip             = os.path.join(local_directory, f"{robotName}_{competence}-{current_date}.zip")
        
        # Levando em consideração que o local_directory é sempre o caminho do projeto
        if mia_db := get_db_in_xlsx(local_directory):
            if not os.path.exists(dir):
                os.makedirs(dir)
            shutil.copyfile(mia_db, os.path.join(dir, 'RelatorioMIA.xlsx'))

        zip_directory(dir, zip)
        # shutil.rmtree(dir)

        return zip
    except Exception as e:
        logger.log(e)
        return False
###
def s3_link_generate(s3_file_path: str, client_id: str | int, robot_id: str | int, mes: int = None, ano: int = None, nome_empresa: str = None
) -> None:
    
    s3              = boto3.client("s3")
    file_name       = os.path.basename(s3_file_path)
    # local_file_path = os.path.join(local_file_path, file_name)

    bucket_name     = os.getenv('BUCKET_NAME')

    if not bucket_name:
        raise ValueError("Variável de ambiente BUCKET_NAME não definida.")

    # Upload de arquivo para o S3
    if mes == None or ano == None:
        s3_file_path_new = f"clients/{client_id}/robot/{robot_id}/{file_name}"
    else:
        s3_file_path_new = f"clients/{client_id}/robot/{robot_id}/{nome_empresa}/{mes}_{ano}/{file_name}"

    try:
        # s3.download_file(bucket_name, s3_file_path_new, local_file_path)
        s3.generate_presigned_url('get_object', Params={'Bucket': bucket_name, 'Key': s3_file_path_new}, ExpiresIn=(((60*60)*24)*365)*5)

        logger.log(
            f"Link gerado com sucesso {s3_file_path_new}."
        )
    except Exception as e:
        logger.log(f"Erro ao gerar link para {s3_file_path_new}: {e}")
        return

    logger.log("Download de arquivos concluído.")


def stepMia(action:str|int, step:str|int, log_name:str, path_log:str, erp_code:int|str='', children_customers: list = [],  archive_name:str='', path_url:str='', end_time: bool=False):
    '''Função para enviar o step para a MIA\n
    :param action: ação que está sendo realizada
    :param step: passo do processo
    :param log_name: nome do arquivo de log. Utilizar logger.get_log_filename()
    :param path_log: caminho do log na S3
    :param erp_code: código do ERP
    :param archive_name: nome do arquivo
    :param path_url: caminho do arquivo na S3
    :param end_time: se o processo terminou
    '''
    
    token = getToken(url, user, passwd)
    
    MES_MIA     = CLI_ARGUMENTS.get('competenceMonth') or ""
    ANO_MIA     = CLI_ARGUMENTS.get('competenceYear') or ""
    instance_id = get_instance_id() or None
    USER_ID     = CLI_ARGUMENTS.get('userId') or 95
    
    if len(sys.argv) > 1:
        robot_id    = sys.argv[1]#pegar via argumento
        customer_id = sys.argv[2]#pegar via argumento
    else:
        logger.log("Não foi possível carregar os argumentos")
        raise Exception('Não foi possível carregar os argumentos na função stepMia()')
    
    steps = getStepFromMIA(url, token, robot_id)
    if len(steps) == 0:
        raise Exception('steps não cadastrados na MIA')

    match step:
        case "START":
            step = steps[0]
        case "ERROR":
            step            = steps[-1]
            actionMensage   = getBugInfo(url, token, robot_id, action)
            action          = f"Erro [{action}] não identificado"
            
            if  actionMensage:
                action = actionMensage.get('error_handling')

        case "FINISH":
            step = steps[-2]
        case _:
            if not isinstance(step, int):
                raise Exception(f'O step [{step}] deve ser um número inteiro')
                      
            step = steps[int(step)]
    
    end_date    = datetime.now().strftime('%Y-%m-%d %H:%M:%S') if end_time else ""
    robot_name  = getRobotNameById(url, token, robot_id, customer_id)
        
    sendStap(url, token, robot_id, customer_id, {
        "instance_id": instance_id,
        "action": action,
        "description": robot_name,
        "step": step,
        "path_log": log_name,
        "path_url_log": path_log,
        "erp_code": erp_code,
        "path_customer": archive_name,
        "path_url_customer": path_url,
        "competence_month": MES_MIA, 
        "competence_year": ANO_MIA,
        "user_id": USER_ID,#95
        "children_customers": children_customers,
        "start_date": start_time,
        "end_date": end_date
    })
    
def get_db_in_xlsx(caminho):
    '''Função para baixar o banco de dados da MIA em formato xlsx'''
    try:
        if not caminho:
            logger.log('Caminho não definido')
            return False
        
        mia_db = None
        for files in os.listdir(caminho):
            if files.endswith('.db'):
                mia_db = files
                break
        
        if not mia_db:
            logger.log('Não foi possível encontrar o arquivo .db')
            return False
        
        sql2excel.SqliteToExcel(os.path.join(caminho, mia_db), os.path.join(caminho), 'RelatorioMIA')
        return os.path.join(caminho, 'RelatorioMIA.xlsx')
    
    except Exception as e:
        logger.log(f'Erro em get_db_in_xlsx(): {e}')
        return False

def getStepComp(url: str, token: str, robot_id: int|str, customer_id: int|str, erp_code: int|str, month: str, year: str) -> str | bool:

    header      = {"Authorization": f"Bearer {token}"}

    response    = requests.get(f'{url}/api/robot_step_log?all_data=true&robot_id={robot_id}&customer_id={customer_id}&erp_code={erp_code}', headers=header) 

    try:
        dados = response.json()['robot_log']['data']
        for log in dados:
            competence = str(log['robot_log']['competence_month']) + '/' + str(log['robot_log']['competence_year'])

            if competence == f'{month}/{year}':
                response = str(log['robot_log']['step'])
                return response

        return False
    except:
        return False


def getStepFromMIA(url: str, token: str, robot_id: int|str) -> str | bool:

    header      = {"Authorization": f"Bearer {token}"}
    response    = requests.get(f'{url}/api/robot_has_steps?robot_id={robot_id}&all_data=true', headers=header)
    
    try:
        data = response.json().get('steps', {}).get('data', [])
    except:
        return False
    
    result = [item['name'] for item in data]

    return result

def getBugInfo(url: str, token: str, robot_id: int|str, bug_id) -> dict | bool:

    header      = {"Authorization": f"Bearer {token}"}
    response    = requests.get(f'{url}/api/bugs?robot_id={robot_id}?id={bug_id}&all_data=true', headers=header)
    
    try:
        data = response.json().get('bugs', {}).get('data', [])[0]
    except:
        return False
    
    return data