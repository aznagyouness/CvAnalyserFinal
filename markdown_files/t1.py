import logging
logger = logging.getLogger(__name__)

class MyNewException(Exception):
    def __init__(self, message: str, code:str="code x"):
        #super().__init__(message)
        self.message = message
        self.code = code

    #def __str__(self):
    #    return f"welcome to the modified exception message  : {self.message} ass hole {self.code}"

try :
    raise MyNewException("this is MyNewNewException")
    
except Exception as e :
    #logger.error(MyNewException("this is MyNewNewException"),exc_info=True)
    logger.error(MyNewException("this is MyNewNewException"))
    print(MyNewException("this is MyNewNewException"))
    print("the message is :", e.message)
    print("the code is :", e.code)
    print("the args is :", e.args)



#raise MyNewException("this is MyNewNewException with rasie ")

"""
def transfer_knowledge(module1,module2):
    import logging  
    logger = logging.getLogger(__name__)
    try : 
        if module1=="math":
            raise ValueError("you are choosing math don't do it")

        if module2=="arabic":
            raise ValueError("you are choosing arabic don't do it")

    except ValueError as ve : 
        print("*"*10)
        logger.warning("this logging is for transfer knowledge function value error : ")
        logger.warning(ve)
        print("*"*10)
        return None
    
    except Exception as e :
        logger.error(e)
        raise e
    
    else :
        return "transfer knowledge has been done"
    
    finally :
        logger.error("finally block has been executed")


transfer_knowledge("kkkk","cccc")

transfer_knowledge("math","arabic")


"""


"""
def transfer_maney(a,b,c):
    try :
        if a<0:
            raise ValueError("a cannot be negative")
        
        if b<0:
            raise ValueError("b cannot be negative")
        if c<0:
            raise ValueError("c cannot be negative")
    except ValueError as ve :
        print("a value error has been occured :", ve)
        raise
    
    except ConnectionError as ce :
        print("a connection error has been occured :", ce)
        return None
    else :
        return a+b+c
    finally :
        print("finally block has been executed")

transfer_maney(10,20,30)

transfer_maney(-10,20,30)

transfer_maney(10,-20,30)
"""